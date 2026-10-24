import asyncio
from datetime import datetime, timedelta, timezone
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
            devices.enqueue_for_users(conn, user_ids, payload["title"], payload.get("body", ""), payload.get("url"),
                                      todo_id=payload.get("todo_id"), action_token=payload.get("token"),
                                      urgent=bool(payload.get("urgent")), bus_message_id=payload.get("bus_message_id"),
                                      reply_token=payload.get("reply_token"), options=payload.get("options"))
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


def notify_payload_threadsafe(user_ids: list[int], payload: dict) -> None:
    """Wie notify_threadsafe, aber mit zusätzlichen Feldern (z. B. bus_message_id, reply_token, options)."""
    import threading

    payload = {**payload, "body": str(payload.get("body", ""))[:200]}
    threading.Thread(target=_send_sync, args=(user_ids, payload), daemon=True).start()


def notify_threadsafe(user_ids: list[int], title: str, body: str, url: str = "/") -> None:
    """Aus synchronen Endpunkten: im Hintergrund senden, nicht blockieren."""
    import threading

    threading.Thread(target=_send_sync, args=(user_ids, {"title": title, "body": body[:200], "url": url}),
                     daemon=True).start()


async def reminder_loop() -> None:
    from . import assistant, backup, mailin, stats, trash

    while True:
        for job in (_check_due, assistant.send_daily_summaries, stats.send_weekly_reviews, mailin.poll_due_accounts,
                    backup.daily_backup, trash.daily_purge):
            try:
                await asyncio.to_thread(job)
            except Exception as exc:
                log.warning("Hintergrund-Lauf %s fehlgeschlagen: %s", job.__name__, exc)
        await asyncio.sleep(60)


def _reminder_text(offset: int | None) -> str:
    if offset is None:
        return "Erinnerung"
    if offset == 0:
        return "Aufgabe fällig"
    if offset % 1440 == 0:
        d = offset // 1440
        return f"Fällig in {d} Tag{'en' if d > 1 else ''}"
    if offset % 60 == 0:
        h = offset // 60
        return f"Fällig in {h} Stunde{'n' if h > 1 else ''}"
    return f"Fällig in {offset} Minuten"


def _check_due() -> None:
    from . import actions  # Zirkelbezug vermeiden

    with session() as conn:
        rows = conn.execute(
            "SELECT r.id, r.offset_min, t.id AS todo_id, r.user_id, t.title, t.priority FROM reminders r JOIN todos t ON t.id = r.todo_id "
            "WHERE r.sent = 0 AND r.remind_at <= ? AND t.done = 0 ORDER BY r.remind_at LIMIT 200", (now(),)).fetchall()
        for r in rows:
            conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (r["id"],))
            conn.execute("UPDATE todos SET reminded = 1 WHERE id = ?", (r["todo_id"],))
            _send_sync([r["user_id"]], {"title": _reminder_text(r["offset_min"]), "body": r["title"][:200], "url": "/#/today",
                                        "todo_id": r["todo_id"], "token": actions.make_token(r["user_id"], r["todo_id"]),
                                        "urgent": r["priority"] == 3})
        conn.execute("DELETE FROM reminders WHERE sent = 1 AND remind_at < ?",
                     ((datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        devices.cleanup(conn)
        devices.release_held(conn)
