import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import push
from .db import get_db, now
from .security import Auth, get_auth

router = APIRouter(prefix="/api/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class Subscription(BaseModel):
    endpoint: str = Field(max_length=1000, pattern=r"^https://")
    keys: Keys


class Unsubscribe(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.get("/key")
def vapid_key(_: Auth = Depends(get_auth)):
    return {"public_key": push.public_key()}


@router.post("/subscribe", status_code=201)
def subscribe(sub: Subscription, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM push_subscriptions WHERE user_id = ?", (auth.id,)).fetchone()[0] >= 20:
        raise HTTPException(422, "Zu viele Geräte registriert.")
    conn.execute(
        "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, created_at) VALUES (?,?,?,?,?) "
        "ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh, auth = excluded.auth",
        (auth.id, sub.endpoint, sub.keys.p256dh, sub.keys.auth, now()))
    return {"ok": True}


@router.post("/unsubscribe", status_code=204)
def unsubscribe(data: Unsubscribe, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ? AND user_id = ?", (data.endpoint, auth.id))


@router.post("/test", status_code=204)
def test_push(auth: Auth = Depends(get_auth)):
    push.notify_threadsafe([auth.id], "Test", "Push-Benachrichtigungen funktionieren.")
