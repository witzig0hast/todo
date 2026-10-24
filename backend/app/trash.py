"""Papierkorb: Gelöschte Aufgaben (inkl. Unteraufgaben, Anhänge, erfasste Zeit) werden 30 Tage als Schnappschuss
aufbewahrt und lassen sich mit ihren ursprünglichen IDs wiederherstellen. Anhang-Dateien bleiben so lange liegen."""
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from . import config, events
from .db import get_db, now, session, tx
from .security import Auth, get_auth
from .todos import audience, can_use_list, sync_reminders, todo_out

log = logging.getLogger("todo.trash")
router = APIRouter(prefix="/api/trash", tags=["trash"])
KEEP_DAYS = 30
# Tabellen, die an einer Aufgabe hängen und mit ihr gesichert/wiederhergestellt werden
DEPENDENTS = [("attachments", "todo_id"), ("time_entries", "todo_id"), ("comments", "todo_id"), ("todo_history", "todo_id"),
              ("todo_deps", "todo_id"), ("todo_deps", "blocked_by_id")]


def _rows(conn: sqlite3.Connection, sql: str, args: tuple) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args)]


def snapshot(conn: sqlite3.Connection, todo: sqlite3.Row) -> dict:
    subs = _rows(conn, "SELECT * FROM todos WHERE parent_id = ? ORDER BY id", (todo["id"],))
    ids = [todo["id"]] + [s["id"] for s in subs]
    marks = ",".join("?" * len(ids))
    deps = {f"{table}.{col}": _rows(conn, f"SELECT * FROM {table} WHERE {col} IN ({marks})", tuple(ids)) for table, col in DEPENDENTS}
    return {"todo": dict(todo), "subs": subs, "deps": deps}


def move(conn: sqlite3.Connection, user_id: int, todos: list[sqlite3.Row], title: str) -> int:
    """Aufgaben (oberste Ebene + ihre Unteraufgaben) in den Papierkorb verschieben. Gibt die Papierkorb-ID zurück."""
    users: set[int] = set()
    geo_owners: set[int] = set()
    with tx(conn):
        trees = []
        for t in todos:
            users |= audience(conn, t)
            if t["location"]:
                geo_owners.add(t["user_id"])
            trees.append(snapshot(conn, t))
        cur = conn.execute("INSERT INTO trash (user_id, title, count, data, deleted_at) VALUES (?,?,?,?,?)",
                           (user_id, title[:300], len(trees), json.dumps(trees, ensure_ascii=False), now()))
        for t in todos:
            conn.execute("DELETE FROM todos WHERE id = ?", (t["id"],))
    from .devices import notify_geofences_changed

    for uid in geo_owners:
        notify_geofences_changed(conn, uid)
    for uid in users:
        events.publish("user", uid, "todo", {"op": "reload"})
    return cur.lastrowid


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    row = {k: v for k, v in row.items() if k in cols}
    try:
        conn.execute(f"INSERT OR IGNORE INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    except sqlite3.IntegrityError:
        pass  # z. B. Abhängigkeit auf eine inzwischen gelöschte Aufgabe


def restore(conn: sqlite3.Connection, user_id: int, trash_id: int) -> int:
    entry = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?", (trash_id, user_id)).fetchone()
    if entry is None:
        raise HTTPException(404, "Nicht im Papierkorb.")
    restored: list[int] = []
    with tx(conn):
        for tree in json.loads(entry["data"]):
            t = tree["todo"]
            owner_ok = conn.execute("SELECT 1 FROM users WHERE id = ?", (t["user_id"],)).fetchone() is not None
            list_ok = t["list_id"] is not None and can_use_list(conn, user_id, t["list_id"])
            if not list_ok:
                t["list_id"] = None
            if not owner_ok or (t["user_id"] != user_id and not list_ok):
                t["user_id"] = user_id  # sonst landete die Aufgabe unsichtbar bei jemand anderem
            if t["parent_id"] is not None and conn.execute("SELECT 1 FROM todos WHERE id = ?", (t["parent_id"],)).fetchone() is None:
                t["parent_id"] = None
            _insert(conn, "todos", t)
            for s in tree["subs"]:
                s["user_id"], s["list_id"] = t["user_id"], t["list_id"]
                _insert(conn, "todos", s)
            for key, rows in tree["deps"].items():
                for r in rows:
                    _insert(conn, key.split(".")[0], r)
            restored.append(t["id"])
        conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
    users: set[int] = set()
    from .devices import notify_geofences_changed

    for tid in restored:
        sync_reminders(conn, tid)
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (tid,)).fetchone()
        if row:
            users |= audience(conn, row)
            if row["location"]:
                notify_geofences_changed(conn, row["user_id"])
    for uid in users:
        events.publish("user", uid, "todo", {"op": "reload"})
    return len(restored)


def _files_of(entry_data: str) -> list[str]:
    return [a["stored_name"] for tree in json.loads(entry_data) for key, rows in tree["deps"].items()
            if key.split(".")[0] == "attachments" for a in rows]


def _drop(conn: sqlite3.Connection, entries: list[sqlite3.Row]) -> None:
    from .attachments import remove_file

    for e in entries:
        conn.execute("DELETE FROM trash WHERE id = ?", (e["id"],))
        for name in _files_of(e["data"]):
            if conn.execute("SELECT 1 FROM attachments WHERE stored_name = ?", (name,)).fetchone() is None:
                remove_file(name)


def purge() -> None:
    """Täglich: abgelaufene Einträge endgültig löschen; verwaiste Anhang-Dateien aufräumen."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with session() as conn:
        _drop(conn, conn.execute("SELECT * FROM trash WHERE deleted_at < ?", (cutoff,)).fetchall())
        folder = config.DATA_DIR / "attachments"
        if not folder.is_dir():
            return
        known = {r["stored_name"] for r in conn.execute("SELECT stored_name FROM attachments")}
        for e in conn.execute("SELECT data FROM trash"):
            known.update(_files_of(e["data"]))
        for f in folder.iterdir():
            try:
                if f.is_file() and f.name not in known and time.time() - f.stat().st_mtime > 86400:
                    f.unlink()
            except OSError as exc:
                log.warning("Aufräumen von %s fehlgeschlagen: %s", f.name, exc)


def daily_purge() -> None:
    with session() as conn:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute("SELECT value FROM settings WHERE key = 'trash_purged_on'").fetchone()
        if row and row["value"] == today:
            return
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('trash_purged_on', ?)", (today,))
    purge()


# ------------------------------------------------------------------ Endpunkte
@router.get("")
def list_trash(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    out = []
    for r in conn.execute("SELECT * FROM trash WHERE user_id = ? ORDER BY id DESC LIMIT 200", (auth.id,)):
        trees = json.loads(r["data"])
        out.append({"id": r["id"], "title": r["title"], "count": r["count"], "deleted_at": r["deleted_at"],
                    "items": [todo_out_safe(t["todo"]) for t in trees[:5]],
                    "subtasks": sum(len(t["subs"]) for t in trees)})
    return {"entries": out, "keep_days": KEEP_DAYS}


def todo_out_safe(row: dict) -> dict:
    d = todo_out(dict(row))
    return {k: d.get(k) for k in ("id", "title", "due_at", "priority", "done", "tags")}


@router.post("/{trash_id}/restore")
def api_restore(trash_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return {"restored": restore(conn, auth.id, trash_id)}


@router.delete("/{trash_id}", status_code=204)
def api_delete(trash_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?", (trash_id, auth.id)).fetchall()
    if not rows:
        raise HTTPException(404, "Nicht im Papierkorb.")
    _drop(conn, rows)


@router.delete("", status_code=204)
def api_empty(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _drop(conn, conn.execute("SELECT * FROM trash WHERE user_id = ?", (auth.id,)).fetchall())
