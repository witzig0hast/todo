"""Aktionen direkt aus Benachrichtigungen ("Erledigt", "Später") - ohne Sitzung, mit signiertem Einmal-Zweck-Token.

Der Token steckt nur in der Benachrichtigung, gilt für genau eine Aufgabe eines Benutzers und läuft nach 7 Tagen ab.
"""
import base64
import hashlib
import hmac
import secrets
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import config
from .db import audit, get_db
from .security import client_ip, enforce_rate

router = APIRouter(prefix="/api", tags=["actions"])
TTL = 7 * 86400
_key: bytes | None = None


def _secret() -> bytes:
    global _key
    if _key is None:
        path = config.DATA_DIR / "action_key"
        if not path.exists():
            path.write_bytes(secrets.token_bytes(32))
            path.chmod(0o600)
        _key = path.read_bytes()
    return _key


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def make_token(user_id: int, todo_id: int, ttl: int = TTL) -> str:
    body = f"{user_id}.{todo_id}.{int(time.time()) + ttl}"
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:18]
    return _b64(body.encode()) + "." + _b64(sig)


def read_token(token: str) -> tuple[int, int]:
    try:
        b, s = token.split(".")
        body = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4))
        sig = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        if not hmac.compare_digest(sig, hmac.new(_secret(), body, hashlib.sha256).digest()[:18]):
            raise ValueError
        uid, tid, exp = (int(x) for x in body.decode().split("."))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(403, "Ungültiger Aktions-Token.") from exc
    if exp < time.time():
        raise HTTPException(403, "Aktions-Token abgelaufen.")
    return uid, tid


class ActionIn(BaseModel):
    token: str = Field(min_length=10, max_length=300)
    action: Literal["done", "snooze"]
    minutes: int = Field(default=10, ge=1, le=7 * 1440)


@router.post("/actions")
def run_action(data: ActionIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"action:{client_ip(request)}", 60, 60)
    user_id, todo_id = read_token(data.token)
    user = conn.execute("SELECT username, status FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None or user["status"] != "approved":
        raise HTTPException(403, "Konto nicht freigegeben.")
    from . import todos  # spät importieren (Zirkelbezug vermeiden)

    if data.action == "done":
        todo = todos.update_todo(conn, user_id, todo_id, {"done": True})
    else:
        todo = todos.snooze(conn, user_id, todo_id, data.minutes)
    audit(conn, user["username"], f"notify_action_{data.action}", str(todo_id), user_id, client_ip(request))
    return {"ok": True, "title": todo["title"]}
