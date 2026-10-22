"""Privater Kalender-Feed (ICS): fällige offene Aufgaben als Termine - abonnierbar in Handy-, Thunderbird-,
Outlook- oder Nextcloud-Kalendern. Zugriff über einen geheimen, widerrufbaren Link."""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from . import config
from .db import get_db
from .security import Auth, enforce_rate, get_auth, sha256
from .todos import list_todos

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: Zeilen nach 75 Oktetts umbrechen (UTF-8-sicher)."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def build_ics(conn: sqlite3.Connection, user_id: int, host: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Todo//Selfhosted//DE", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Todo", "REFRESH-INTERVAL;VALUE=DURATION:PT30M", "X-PUBLISHED-TTL:PT30M"]
    for t in list_todos(conn, user_id, done=False, limit=2000):
        if t["parent_id"] or not t["due_at"]:
            continue
        start = datetime.strptime(t["due_at"], "%Y-%m-%dT%H:%M:%SZ")
        end = start + timedelta(minutes=30)
        prio = {3: "1", 2: "5", 1: "9"}.get(t["priority"])
        lines += ["BEGIN:VEVENT", f"UID:todo-{t['id']}@{host}", f"DTSTAMP:{stamp}",
                  f"DTSTART:{start:%Y%m%dT%H%M%SZ}", f"DTEND:{end:%Y%m%dT%H%M%SZ}", f"SUMMARY:{_esc(t['title'])}"]
        if t["notes"]:
            lines.append(f"DESCRIPTION:{_esc(t['notes'][:2000])}")
        if t["tags"]:
            lines.append("CATEGORIES:" + ",".join(_esc(g) for g in t["tags"]))
        if prio:
            lines.append(f"PRIORITY:{prio}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


@router.get("/feed")
def feed_status(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT ics_token_hash FROM user_settings WHERE user_id = ?", (auth.id,)).fetchone()
    return {"enabled": bool(row and row["ics_token_hash"])}


@router.post("/feed")
def create_feed(request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Neuen geheimen Link erzeugen (ein alter wird ungültig). Nur hier im Klartext."""
    token = "ics_" + secrets.token_urlsafe(32)
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (auth.id,))
    conn.execute("UPDATE user_settings SET ics_token_hash = ? WHERE user_id = ?", (sha256(token), auth.id))
    base = config.PUBLIC_URL or str(request.base_url).rstrip("/")
    return {"url": f"{base}/api/calendar/{token}.ics"}


@router.delete("/feed", status_code=204)
def delete_feed(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("UPDATE user_settings SET ics_token_hash = NULL WHERE user_id = ?", (auth.id,))


@router.get("/{token}.ics")
def ics(token: str, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"ics:{sha256(token)[:16]}", 60, 3600)
    row = conn.execute("SELECT s.user_id FROM user_settings s JOIN users u ON u.id = s.user_id "
                       "WHERE s.ics_token_hash = ? AND u.status = 'approved'", (sha256(token),)).fetchone()
    if row is None:
        raise HTTPException(404, "Unbekannter Kalender.")
    host = (config.PUBLIC_URL.split("://")[-1] if config.PUBLIC_URL else request.url.hostname) or "todo"
    return Response(build_ics(conn, row["user_id"], host), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="todo.ics"', "Cache-Control": "private, max-age=300"})
