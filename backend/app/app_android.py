"""Schnittstellen für die Android-App mit Geräte-Token: Widget-Daten, Schnellerfassung, Abhaken – und Verteilung von
App-Updates über den eigenen Server (CI oder Admin lädt die APK hoch, die App meldet „Update verfügbar“)."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config
from .db import audit, get_db, now
from .devices import get_device
from .integrations import summary
from .recurrence import FMT, user_tz
from .security import Auth, client_ip, get_auth, sha256
from .todos import QuickIn, api_quick_create, list_todos, update_todo

router = APIRouter(prefix="/api/app", tags=["android"])
MAX_APK = 60 * 1024 * 1024


def _dir():
    d = config.DATA_DIR / "app"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ Widget & Schnellerfassung (Geräte-Token)
@router.get("/widget")
def widget(device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    uid = device["user_id"]
    local = datetime.now(timezone.utc).astimezone(user_tz(conn, uid))
    end = local.replace(hour=23, minute=59, second=59).astimezone(timezone.utc).strftime(FMT)
    current = now()
    todos = [t for t in list_todos(conn, uid, done=False, limit=2000) if not t["parent_id"]]
    today = [t for t in todos if t["due_at"] and t["due_at"] <= end]
    today.sort(key=lambda t: (t["due_at"] >= current, -t["priority"], t["due_at"]))  # überfällige zuerst
    rest = sorted((t for t in todos if t not in today), key=lambda t: (t["due_at"] is None, t["due_at"] or "", -t["priority"]))
    items = (today + rest)[:8]
    s = summary(conn, uid)
    return {"open": s["open"], "today": s["today"], "overdue": s["overdue"], "updated_at": current,
            "items": [{"id": t["id"], "title": t["title"], "due_at": t["due_at"], "priority": t["priority"],
                       "overdue": bool(t["due_at"] and t["due_at"] < current), "today": t in today} for t in items]}


class AppQuick(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class _AsUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


@router.post("/quick", status_code=201)
def quick(data: AppQuick, device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    t = api_quick_create(QuickIn(text=data.text), _AsUser(device["user_id"]), conn)
    return {"id": t["id"], "title": t["title"], "due_at": t["due_at"]}


@router.post("/todos/{todo_id}/done")
def done(todo_id: int, device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    t = update_todo(conn, device["user_id"], todo_id, {"done": True}, actor=f"{device['name']} (Widget)")
    return {"id": t["id"], "done": t["done"]}


# ------------------------------------------------------------------ App-Updates
def _meta() -> dict | None:
    p = _dir() / "android.json"
    return json.loads(p.read_text()) if p.exists() and (_dir() / "todo.apk").exists() else None


def _device_or_session(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> int:
    if request.headers.get("authorization", "").lower().startswith("bearer tdv_"):
        return get_device(request, conn)["user_id"]
    return get_auth(request, conn).id


@router.get("/android")
def android_meta(_: int = Depends(_device_or_session)):
    m = _meta()
    return {"available": bool(m), **(m or {})}


@router.get("/android/download")
def android_download(_: int = Depends(_device_or_session)):
    m = _meta()
    if not m:
        raise HTTPException(404, "Noch keine App-Version hochgeladen.")
    return FileResponse(_dir() / "todo.apk", media_type="application/vnd.android.package-archive",
                        filename=f"todo-{m['version_name']}.apk")


def _uploader(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> str:
    """Admin per Sitzung (Oberfläche) oder per API-Token mit Schreibrecht (z. B. aus GitHub Actions)."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer tdk_"):
        row = conn.execute("SELECT u.username, u.role, u.status, t.scopes FROM api_tokens t JOIN users u ON u.id = t.user_id "
                           "WHERE t.token_hash = ?", (sha256(header[7:].strip()),)).fetchone()
        if row is None or row["status"] != "approved" or row["role"] != "admin" or "write" not in row["scopes"].split(","):
            raise HTTPException(403, "Nur Admins mit Schreib-Token dürfen App-Versionen hochladen.")
        return row["username"]
    auth = get_auth(request, conn)
    if not auth.is_admin:
        raise HTTPException(403, "Nur für Administratoren.")
    return auth.user["username"]


@router.post("/android", status_code=201)
async def android_upload(request: Request, version_code: int = Query(ge=1, le=2_100_000_000),
                         version_name: str = Query(min_length=1, max_length=40, pattern=r"^[0-9A-Za-z.\-+_]+$"),
                         who: str = Depends(_uploader), conn: sqlite3.Connection = Depends(get_db)):
    data = await request.body()
    if len(data) < 1024 or len(data) > MAX_APK or not data.startswith(b"PK\x03\x04") or b"AndroidManifest.xml" not in data:
        raise HTTPException(415, "Das ist keine APK-Datei.")
    old = _meta()
    if old and version_code < old["version_code"]:
        raise HTTPException(409, f"Version {version_code} ist älter als die vorhandene ({old['version_code']}).")
    tmp = _dir() / "todo.apk.part"
    tmp.write_bytes(data)
    tmp.replace(_dir() / "todo.apk")
    meta = {"version_code": version_code, "version_name": version_name, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "uploaded_at": now(), "uploaded_by": who}
    (_dir() / "android.json").write_text(json.dumps(meta))
    audit(conn, who, "android_upload", f"{version_name} ({version_code})", None, client_ip(request))
    return meta

