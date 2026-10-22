"""Geräte (z. B. die Android-App): Registrierung mit eigenem Geräte-Token, gezielte Nachrichten an einzelne Geräte,
Live-Zustellung per SSE (`/stream`) mit Warteschlange für Offline-Zeiten und Bestätigung (`ack`)."""
import asyncio
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from . import events
from .events import sse_response
from .db import audit, get_db, now, session
from .security import Auth, client_ip, enforce_rate, get_auth, sha256

router = APIRouter(prefix="/api/devices", tags=["devices"])
MAX_DEVICES = 20
_PATH = re.compile(r"^/[^\s\\]*$")


def _check_url(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not _PATH.match(v) or v.startswith("//") or len(v) > 200:
        raise ValueError("url muss ein relativer Pfad sein, z. B. /#/today.")
    return v


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    platform: Literal["android", "other"] = "android"
    app_version: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip() or "Gerät"


class SendIn(BaseModel):
    device_id: int | None = None  # None = an alle Geräte
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(default="", max_length=500)
    url: str | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _check_url(v)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


def message_out(r: sqlite3.Row) -> dict:
    keys = r.keys()
    return {"id": r["id"], "title": r["title"], "body": r["body"], "url": r["url"], "created_at": r["created_at"],
            "todo_id": r["todo_id"] if "todo_id" in keys else None,
            "action_token": r["action_token"] if "action_token" in keys else None}


def _unique_name(conn: sqlite3.Connection, user_id: int, name: str, exclude_id: int | None = None) -> str:
    candidate, n = name, 1
    while conn.execute("SELECT 1 FROM devices WHERE user_id = ? AND name = ? COLLATE NOCASE AND id != ?",
                       (user_id, candidate, exclude_id or 0)).fetchone():
        n += 1
        candidate = f"{name[:55]} ({n})"
    return candidate


def enqueue(conn: sqlite3.Connection, user_id: int, title: str, body: str = "", url: str | None = None,
            device_id: int | None = None, todo_id: int | None = None, action_token: str | None = None) -> list[dict]:
    """Legt die Nachricht für ein Gerät (oder alle Geräte des Benutzers) in die Warteschlange und stellt sie live zu."""
    if device_id is not None:
        rows = conn.execute("SELECT id FROM devices WHERE id = ? AND user_id = ?", (device_id, user_id)).fetchall()
        if not rows:
            raise LookupError("Gerät nicht gefunden.")
    else:
        rows = conn.execute("SELECT id FROM devices WHERE user_id = ?", (user_id,)).fetchall()
    out = []
    for d in rows:
        cur = conn.execute("INSERT INTO device_messages (user_id, device_id, title, body, url, created_at, todo_id, action_token)"
                           " VALUES (?,?,?,?,?,?,?,?)", (user_id, d["id"], title, body, url, now(), todo_id, action_token))
        msg = message_out(conn.execute("SELECT * FROM device_messages WHERE id = ?", (cur.lastrowid,)).fetchone())
        events.publish("device", d["id"], "message", msg, event_id=msg["id"])
        out.append({**msg, "device_id": d["id"]})
    return out


def enqueue_for_users(conn: sqlite3.Connection, user_ids: list[int], title: str, body: str = "", url: str | None = None,
                      todo_id: int | None = None, action_token: str | None = None) -> None:
    for uid in user_ids:
        enqueue(conn, uid, title, body, url, todo_id=todo_id, action_token=action_token)


def cleanup(conn: sqlite3.Connection) -> None:
    t = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    conn.execute("DELETE FROM device_messages WHERE (delivered_at IS NOT NULL AND delivered_at < ?) OR created_at < ?",
                 ((t - timedelta(days=7)).strftime(fmt), (t - timedelta(days=30)).strftime(fmt)))


# ------------------------------------------------------------------ Geräte-Authentifizierung (Bearer-Token)
def get_device(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Geräte-Token fehlt.")
    row = conn.execute("SELECT d.*, u.status AS user_status FROM devices d JOIN users u ON u.id = d.user_id "
                       "WHERE d.token_hash = ?", (sha256(auth[7:].strip()),)).fetchone()
    if row is None or row["user_status"] != "approved":
        raise HTTPException(401, "Ungültiger Geräte-Token.")
    conn.execute("UPDATE devices SET last_seen_at = ? WHERE id = ?", (now(), row["id"]))
    return row


# ------------------------------------------------------------------ Nutzer-API (Cookie-Sitzung)
@router.post("/register", status_code=201)
def register(data: RegisterIn, request: Request, auth: Auth = Depends(get_auth),
             conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"device-reg:{auth.id}", 10, 3600)
    if conn.execute("SELECT COUNT(*) FROM devices WHERE user_id = ?", (auth.id,)).fetchone()[0] >= MAX_DEVICES:
        raise HTTPException(422, f"Maximal {MAX_DEVICES} Geräte pro Konto.")
    token = "tdv_" + secrets.token_urlsafe(32)
    name = _unique_name(conn, auth.id, data.name)
    cur = conn.execute("INSERT INTO devices (user_id, name, platform, app_version, token_hash, created_at, last_seen_at)"
                       " VALUES (?,?,?,?,?,?,?)", (auth.id, name, data.platform, data.app_version, sha256(token), now(), now()))
    audit(conn, auth.user["username"], "device_register", f"{name} ({data.platform})", auth.id, client_ip(request))
    return {"id": cur.lastrowid, "name": name, "token": token}  # Token nur hier im Klartext


@router.get("")
def list_devices(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT d.*, (SELECT COUNT(*) FROM device_messages m WHERE m.device_id = d.id AND m.delivered_at IS NULL) AS pending "
        "FROM devices d WHERE d.user_id = ? ORDER BY d.id", (auth.id,)).fetchall()
    return {"devices": [{"id": r["id"], "name": r["name"], "platform": r["platform"], "app_version": r["app_version"],
                         "created_at": r["created_at"], "last_seen_at": r["last_seen_at"], "pending": r["pending"],
                         "online": events.has_subscribers("device", r["id"])} for r in rows]}


@router.post("/send")
def send(data: SendIn, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"device-send:{auth.id}", 60, 60)
    try:
        sent = enqueue(conn, auth.id, data.title, data.body, data.url, data.device_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not sent:
        raise HTTPException(404, "Keine Geräte registriert.")
    return {"sent": len(sent), "online": sum(events.has_subscribers("device", m["device_id"]) for m in sent)}


@router.delete("/self", status_code=204)
def unregister_self(device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM devices WHERE id = ?", (device["id"],))


@router.patch("/{device_id}")
def rename(device_id: int, data: RenameIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if not conn.execute("SELECT 1 FROM devices WHERE id = ? AND user_id = ?", (device_id, auth.id)).fetchone():
        raise HTTPException(404, "Gerät nicht gefunden.")
    name = _unique_name(conn, auth.id, data.name.strip() or "Gerät", exclude_id=device_id)
    conn.execute("UPDATE devices SET name = ? WHERE id = ?", (name, device_id))
    return {"id": device_id, "name": name}


@router.delete("/{device_id}", status_code=204)
def remove(device_id: int, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM devices WHERE id = ? AND user_id = ?", (device_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Gerät nicht gefunden.")
    audit(conn, auth.user["username"], "device_delete", str(device_id), auth.id, client_ip(request))


# ------------------------------------------------------------------ Geräte-API (Bearer-Token, von der App genutzt)
def _device_exists(device_id: int) -> bool:
    with session() as conn:
        return conn.execute("SELECT 1 FROM devices WHERE id = ?", (device_id,)).fetchone() is not None


def _pending(device_id: int) -> list[sqlite3.Row]:
    with session() as conn:
        return conn.execute("SELECT * FROM device_messages WHERE device_id = ? AND delivered_at IS NULL ORDER BY id LIMIT 200",
                            (device_id,)).fetchall()


@router.get("/stream")
async def stream(request: Request, device: sqlite3.Row = Depends(get_device)):
    """SSE: zuerst alle unbestätigten Nachrichten, danach live. Der Client bestätigt jede per `POST /messages/{id}/ack`."""
    device_id = device["id"]
    q = events.subscribe("device", device_id)  # zuerst abonnieren, dann Rückstand lesen: keine Lücke

    async def gen():
        import json
        sent: set[int] = set()
        try:
            yield "retry: 3000\n: connected\n\n"
            for r in await asyncio.to_thread(_pending, device_id):
                sent.add(r["id"])
                yield f"id: {r['id']}\nevent: message\ndata: {json.dumps(message_out(r), ensure_ascii=False)}\n\n"
            while not await request.is_disconnected():
                try:
                    item = await asyncio.wait_for(q.get(), timeout=20)
                except asyncio.TimeoutError:
                    if not await asyncio.to_thread(_device_exists, device_id):
                        return  # Gerät wurde entfernt -> Verbindung beenden, App meldet sich ab
                    yield ": ping\n\n"
                    continue
                m = re.match(r"id: (\d+)\n", item)
                if m and int(m.group(1)) in sent:
                    continue  # schon als Rückstand gesendet
                yield item
        finally:
            events.unsubscribe("device", device_id, q)

    return sse_response(gen())


@router.post("/messages/{message_id}/ack", status_code=204)
def ack(message_id: int, device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("UPDATE device_messages SET delivered_at = ? WHERE id = ? AND device_id = ? AND delivered_at IS NULL",
                       (now(), message_id, device["id"]))
    if cur.rowcount == 0 and not conn.execute("SELECT 1 FROM device_messages WHERE id = ? AND device_id = ?",
                                              (message_id, device["id"])).fetchone():
        raise HTTPException(404, "Nachricht nicht gefunden.")
