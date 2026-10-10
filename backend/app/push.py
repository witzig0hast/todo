import asyncio
import base64
import json
import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from . import config, devices
from .db import now, session

log = logging.getLogger("todo.push")


def _key_path() -> Path:
    return config.DATA_DIR / "vapid_private.pem"


def ensure_vapid() -> None:
    path = _key_path()
    if not path.exists():
        v = Vapid()
        v.generate_keys()
        v.save_key(str(path))
        path.chmod(0o600)


def public_key() -> str:
    v = Vapid.from_file(str(_key_path()))
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _send_sync(user_ids: list[int], payload: dict) -> None:
    if not user_ids:
        return
    marks = ",".join("?" * len(user_ids))
    with session() as conn:
        try:  # native Geräte (Android-App): Warteschlange + Live-Zustellung
            devices.enqueue_for_users(conn, user_ids, payload["title"], payload.get("body", ""), payload.get("url"))
        except Exception as exc:
            log.warning("Geräte-Zustellung fehlgeschlagen: %s", exc)
        subs = conn.execute(f"SELECT * FROM push_subscriptions WHERE user_id IN ({marks})", user_ids).fetchall()
        for s in subs:
            try:
                webpush(
                    subscription_info={"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=str(_key_path()),
                    vapid_claims={"sub": config.VAPID_SUBJECT},
                    ttl=3600,
                )
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):
                    conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (s["id"],))
                else:
                    log.warning("Push fehlgeschlagen (%s): %s", status, exc)
            except Exception as exc:  # Netzwerkfehler dürfen nie die Anfrage stören
                log.warning("Push fehlgeschlagen: %s", exc)


async def notify(user_ids: list[int], title: str, body: str, url: str = "/") -> None:
    await asyncio.to_thread(_send_sync, user_ids, {"title": title, "body": body[:200], "url": url})


def notify_threadsafe(user_ids: list[int], title: str, body: str, url: str = "/") -> None:
    """Aus synchronen Endpunkten: im Hintergrund senden, nicht blockieren."""
    import threading

    threading.Thread(target=_send_sync, args=(user_ids, {"title": title, "body": body[:200], "url": url}),
                     daemon=True).start()


async def reminder_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_check_due)
        except Exception as exc:
            log.warning("Erinnerungs-Lauf fehlgeschlagen: %s", exc)
        await asyncio.sleep(60)


def _check_due() -> None:
    with session() as conn:
        rows = conn.execute(
            "SELECT id, user_id, title FROM todos WHERE done = 0 AND reminded = 0 AND due_at IS NOT NULL AND due_at <= ?",
            (now(),),
        ).fetchall()
        for r in rows:
            conn.execute("UPDATE todos SET reminded = 1 WHERE id = ?", (r["id"],))
            _send_sync([r["user_id"]], {"title": "Aufgabe fällig", "body": r["title"][:200], "url": "/"})
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        devices.cleanup(conn)
