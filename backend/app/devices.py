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
    urgent: bool = False  # auch während der Ruhezeit zustellen
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(default="", max_length=500)
    url: str | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _check_url(v)


_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class DevicePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    quiet_start: str | None = None
    quiet_end: str | None = None

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not _HHMM.match(v):
            raise ValueError("Uhrzeit im Format HH:MM.")
        return v


def quiet_until(conn: sqlite3.Connection, device: sqlite3.Row, at: datetime | None = None) -> str | None:
    """Liegt `at` in der Ruhezeit des Geräts, das UTC-Ende der Ruhezeit, sonst None."""
    if not device["quiet_start"] or not device["quiet_end"] or device["quiet_start"] == device["quiet_end"]:
        return None
    from .recurrence import FMT, user_tz

    tz = user_tz(conn, device["user_id"])
    local = (at or datetime.now(timezone.utc)).astimezone(tz)
    sh, sm = map(int, device["quiet_start"].split(":"))
    eh, em = map(int, device["quiet_end"].split(":"))
    cur, start, end = local.hour * 60 + local.minute, sh * 60 + sm, eh * 60 + em
    inside = start <= cur < end if start < end else (cur >= start or cur < end)
    if not inside:
        return None
    end_dt = local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if end_dt <= local:
        end_dt += timedelta(days=1)
    return end_dt.astimezone(timezone.utc).strftime(FMT)


def message_out(r: sqlite3.Row) -> dict:
    keys = r.keys()
    return {"id": r["id"], "title": r["title"], "body": r["body"], "url": r["url"], "created_at": r["created_at"],
            "todo_id": r["todo_id"] if "todo_id" in keys else None,
            "action_token": r["action_token"] if "action_token" in keys else None,
            "urgent": bool(r["urgent"]) if "urgent" in keys else False}


def _unique_name(conn: sqlite3.Connection, user_id: int, name: str, exclude_id: int | None = None) -> str:
    candidate, n = name, 1
    while conn.execute("SELECT 1 FROM devices WHERE user_id = ? AND name = ? COLLATE NOCASE AND id != ?",
                       (user_id, candidate, exclude_id or 0)).fetchone():
        n += 1
        candidate = f"{name[:55]} ({n})"
    return candidate


def enqueue(conn: sqlite3.Connection, user_id: int, title: str, body: str = "", url: str | None = None,
            device_id: int | None = None, todo_id: int | None = None, action_token: str | None = None,
            urgent: bool = False) -> list[dict]:
    """Legt die Nachricht für ein Gerät (oder alle Geräte des Benutzers) in die Warteschlange und stellt sie live zu."""
    if device_id is not None:
        rows = conn.execute("SELECT * FROM devices WHERE id = ? AND user_id = ?", (device_id, user_id)).fetchall()
        if not rows:
            raise LookupError("Gerät nicht gefunden.")
    else:
        rows = conn.execute("SELECT * FROM devices WHERE user_id = ?", (user_id,)).fetchall()
    out = []
    for d in rows:
        hold = None if urgent else quiet_until(conn, d)
        cur = conn.execute("INSERT INTO device_messages (user_id, device_id, title, body, url, created_at, todo_id, action_token,"
                           " urgent, deliver_after) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (user_id, d["id"], title, body, url, now(), todo_id, action_token, int(urgent), hold))
        msg = message_out(conn.execute("SELECT * FROM device_messages WHERE id = ?", (cur.lastrowid,)).fetchone())
        if hold is None:
            events.publish("device", d["id"], "message", msg, event_id=msg["id"])
        out.append({**msg, "device_id": d["id"], "held_until": hold})
    return out


def enqueue_for_users(conn: sqlite3.Connection, user_ids: list[int], title: str, body: str = "", url: str | None = None,
                      todo_id: int | None = None, action_token: str | None = None, urgent: bool = False) -> None:
    for uid in user_ids:
        enqueue(conn, uid, title, body, url, todo_id=todo_id, action_token=action_token, urgent=urgent)


def release_held(conn: sqlite3.Connection) -> int:
    """Nach Ende der Ruhezeit: zurückgehaltene Nachrichten live zustellen (verbundene Geräte)."""
    rows = conn.execute("SELECT * FROM device_messages WHERE deliver_after IS NOT NULL AND deliver_after <= ? "
                        "AND delivered_at IS NULL", (now(),)).fetchall()
    for r in rows:
        conn.execute("UPDATE device_messages SET deliver_after = NULL WHERE id = ?", (r["id"],))
        events.publish("device", r["device_id"], "message", message_out(r), event_id=r["id"])
    return len(rows)


def notify_geofences_changed(conn: sqlite3.Connection, user_id: int) -> None:
    for d in conn.execute("SELECT id FROM devices WHERE user_id = ?", (user_id,)):
        events.publish("device", d["id"], "geofences", {"changed": True})


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
                         "quiet_start": r["quiet_start"], "quiet_end": r["quiet_end"],
                         "online": events.has_subscribers("device", r["id"])} for r in rows]}


@router.post("/send")
def send(data: SendIn, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"device-send:{auth.id}", 60, 60)
    try:
        sent = enqueue(conn, auth.id, data.title, data.body, data.url, data.device_id, urgent=data.urgent)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not sent:
        raise HTTPException(404, "Keine Geräte registriert.")
    return {"sent": len(sent), "held": sum(1 for m in sent if m["held_until"]),
            "online": sum(events.has_subscribers("device", m["device_id"]) for m in sent if not m["held_until"])}


@router.delete("/self", status_code=204)
def unregister_self(device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM devices WHERE id = ?", (device["id"],))


@router.get("/geofences")
def geofences(device: sqlite3.Row = Depends(get_device), conn: sqlite3.Connection = Depends(get_db)):
    """Orte offener Aufgaben, an denen die App erinnern soll (mit Aktions-Token für Erledigt/Später)."""
    import json

    from .actions import make_token

    out = []
    for r in conn.execute("SELECT id, title, location FROM todos WHERE user_id = ? AND done = 0 AND location IS NOT NULL "
                          "ORDER BY id LIMIT 90", (device["user_id"],)):  # Android erlaubt max. ~100 Annäherungsalarme
        loc = json.loads(r["location"])
        out.append({"todo_id": r["id"], "title": r["title"], "name": loc.get("name") or "", "lat": loc["lat"],
                    "lon": loc["lon"], "radius": loc["radius"], "token": make_token(device["user_id"], r["id"])})
    return {"geofences": out}


@router.patch("/{device_id}")
def patch_device(device_id: int, data: DevicePatch, auth: Auth = Depends(get_auth),
                 conn: sqlite3.Connection = Depends(get_db)):
    if not conn.execute("SELECT 1 FROM devices WHERE id = ? AND user_id = ?", (device_id, auth.id)).fetchone():
        raise HTTPException(404, "Gerät nicht gefunden.")
    patch = data.model_dump(exclude_unset=True)
    if patch.get("name"):
        conn.execute("UPDATE devices SET name = ? WHERE id = ?",
                     (_unique_name(conn, auth.id, patch["name"].strip() or "Gerät", exclude_id=device_id), device_id))
    if "quiet_start" in patch or "quiet_end" in patch:
        conn.execute("UPDATE devices SET quiet_start = ?, quiet_end = ? WHERE id = ?",
                     (patch.get("quiet_start"), patch.get("quiet_end"), device_id))
    r = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    return {"id": device_id, "name": r["name"], "quiet_start": r["quiet_start"], "quiet_end": r["quiet_end"]}


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
        return conn.execute("SELECT * FROM device_messages WHERE device_id = ? AND delivered_at IS NULL "
                            "AND (deliver_after IS NULL OR deliver_after <= ?) ORDER BY id LIMIT 200",
                            (device_id, now())).fetchall()


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
