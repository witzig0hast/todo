"""Betrieb: tägliches, konsistentes SQLite-Backup (Online-Backup-API) mit Aufbewahrung, Admin-Download,
sowie Datenexport für jeden Benutzer (JSON komplett, CSV für Aufgaben)."""
import csv
import io
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from . import config
from .db import connect, get_db, session
from .security import Auth, enforce_rate, get_auth, require_admin
from .todos import list_todos

log = logging.getLogger("todo.backup")
router = APIRouter(prefix="/api", tags=["backup"])
KEEP = int(os.getenv("BACKUP_KEEP", "14"))
_NAME = re.compile(r"^todo-\d{8}-\d{6}\.db$")


def _dir():
    d = config.DATA_DIR / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_backup() -> str:
    name = f"todo-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
    target = _dir() / name
    src = connect()
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)  # konsistent, auch während geschrieben wird
    finally:
        dst.close()
        src.close()
    target.chmod(0o600)
    backups = sorted(p for p in _dir().iterdir() if _NAME.match(p.name))
    for old in backups[:-KEEP] if KEEP > 0 else []:
        old.unlink(missing_ok=True)
    return name


def daily_backup() -> None:
    """Vom Hintergrund-Lauf jede Minute aufgerufen: höchstens ein Backup pro Tag (UTC)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with session() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'last_backup'").fetchone()
        if row and row["value"] == today:
            return
        conn.execute("INSERT INTO settings (key, value) VALUES ('last_backup', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (today,))
    try:
        make_backup()
    except (OSError, sqlite3.Error) as exc:
        log.warning("Backup fehlgeschlagen: %s", exc)


@router.get("/admin/backups")
def list_backups(_: Auth = Depends(require_admin)):
    items = sorted((p for p in _dir().iterdir() if _NAME.match(p.name)), reverse=True)
    return {"backups": [{"name": p.name, "size": p.stat().st_size} for p in items], "keep": KEEP}


@router.post("/admin/backups", status_code=201)
def create_backup(auth: Auth = Depends(require_admin)):
    enforce_rate(f"backup:{auth.id}", 5, 3600)
    return {"name": make_backup()}


@router.get("/admin/backups/{name}")
def download_backup(name: str, _: Auth = Depends(require_admin)):
    if not _NAME.match(name) or not (_dir() / name).exists():
        raise HTTPException(404, "Backup nicht gefunden.")
    return FileResponse(_dir() / name, media_type="application/vnd.sqlite3", filename=name,
                        headers={"Cache-Control": "no-store"})


def export_data(conn: sqlite3.Connection, user_id: int) -> dict:
    u = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    rows = lambda sql: [dict(r) for r in conn.execute(sql, (user_id,))]  # noqa: E731
    return {
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "todo-export/1",
        "user": dict(u),
        "lists": rows("SELECT id, name, color, created_at FROM lists WHERE user_id = ?"),
        "todos": list_todos(conn, user_id, limit=100000),
        "filters": [{**f, "query": json.loads(f["query"])} for f in rows("SELECT id, name, query FROM saved_filters WHERE user_id = ?")],
        "rules": [{**r, "match": json.loads(r["match"]), "action": json.loads(r["action"])}
                  for r in rows("SELECT id, name, enabled, match, action, fire_count FROM rules WHERE user_id = ?")],
        "agents": rows("SELECT id, name, description, scopes, created_at FROM agents WHERE user_id = ?"),
        "messages": rows("SELECT id, from_label, to_label, kind, content, task_type, payload, status, result, created_at "
                         "FROM messages WHERE user_id = ? ORDER BY id"),
        "devices": rows("SELECT id, name, platform, created_at FROM devices WHERE user_id = ?"),
    }


@router.get("/export")
def export(format: str = Query("json", pattern="^(json|csv)$"), auth: Auth = Depends(get_auth),
           conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"export:{auth.id}", 10, 600)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if format == "json":
        body = json.dumps(export_data(conn, auth.id), ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="todo-export-{stamp}.json"'})
    lists = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM lists")}
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["id", "titel", "notizen", "liste", "priorität", "fällig (UTC)", "erledigt", "erledigt am", "tags", "wiederholung",
                "übergeordnet", "erstellt"])
    for t in list_todos(conn, auth.id, limit=100000):
        cells = [t["id"], t["title"], t["notes"], lists.get(t["list_id"], ""), t["priority"], t["due_at"] or "", "ja" if t["done"] else "nein",
                 t["done_at"] or "", " ".join(t["tags"]), t["recurrence_text"] or "", t["parent_id"] or "", t["created_at"]]
        # Schutz vor Formel-Injection in Tabellenprogrammen
        w.writerow([("'" + c) if isinstance(c, str) and c[:1] in ("=", "+", "-", "@", "\t", "\r") else c for c in cells])
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="todo-export-{stamp}.csv"'})
