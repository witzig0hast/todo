"""Einladungslinks: Admins erzeugen einen Link mit Ablaufdatum und Nutzungszahl; wer sich damit registriert, ist sofort
freigegeben. Der Link enthält ein zufälliges Geheimnis, gespeichert wird nur dessen Hash."""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import config
from .db import audit, get_db, now
from .security import Auth, client_ip, enforce_rate, require_admin, sha256

router = APIRouter(prefix="/api", tags=["invites"])


class InviteIn(BaseModel):
    note: str = Field(default="", max_length=80)
    days: int = Field(default=7, ge=1, le=60)
    max_uses: int = Field(default=1, ge=1, le=50)


def find_valid(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    if not token or len(token) > 100:
        return None
    row = conn.execute("SELECT * FROM invites WHERE token_hash = ?", (sha256(token),)).fetchone()
    if row is None or row["uses"] >= row["max_uses"] or row["expires_at"] < now():
        return None
    return row


def consume(conn: sqlite3.Connection, token: str) -> sqlite3.Row:
    """Innerhalb der Registrierungs-Transaktion aufrufen."""
    row = find_valid(conn, token)
    if row is None:
        raise HTTPException(400, "Die Einladung ist ungültig, abgelaufen oder schon verbraucht.")
    conn.execute("UPDATE invites SET uses = uses + 1 WHERE id = ?", (row["id"],))
    return row


def _out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "note": r["note"], "max_uses": r["max_uses"], "uses": r["uses"], "expires_at": r["expires_at"],
            "created_at": r["created_at"], "active": r["uses"] < r["max_uses"] and r["expires_at"] >= now()}


@router.get("/admin/invites")
def list_invites(_: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    return {"invites": [_out(r) for r in conn.execute("SELECT * FROM invites ORDER BY id DESC LIMIT 100")]}


@router.post("/admin/invites", status_code=201)
def create_invite(data: InviteIn, request: Request, admin: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=data.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = conn.execute("INSERT INTO invites (token_hash, created_by, note, max_uses, expires_at, created_at) VALUES (?,?,?,?,?,?)",
                       (sha256(token), admin.id, data.note.strip(), data.max_uses, expires, now()))
    audit(conn, admin.user["username"], "invite_created", f"uses={data.max_uses} days={data.days} {data.note}".strip(), admin.id, client_ip(request))
    base = config.PUBLIC_URL or str(request.base_url).rstrip("/")
    return {**_out(conn.execute("SELECT * FROM invites WHERE id = ?", (cur.lastrowid,)).fetchone()), "url": f"{base}/?invite={token}"}


@router.delete("/admin/invites/{invite_id}", status_code=204)
def delete_invite(invite_id: int, _: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("DELETE FROM invites WHERE id = ?", (invite_id,)).rowcount == 0:
        raise HTTPException(404, "Einladung nicht gefunden.")


@router.get("/auth/invite/{token}")
def check_invite(token: str, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"invite-check:{client_ip(request)}", 30, 600)
    row = find_valid(conn, token)
    if row is None:
        return {"valid": False}
    by = conn.execute("SELECT username FROM users WHERE id = ?", (row["created_by"],)).fetchone()
    return {"valid": True, "note": row["note"], "by": by["username"] if by else None}
