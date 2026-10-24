"""Statusseite für Admins: Erreichbarkeit von Ollama/Whisper, Push, Mail-Abruf, Kanäle, Datenbank, Speicher, Hintergrundjobs."""
import asyncio
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends

from . import config, events, push
from .db import get_db, now
from .recurrence import user_tz
from .security import Auth, require_admin

router = APIRouter(prefix="/api/admin", tags=["status"])


def _check(name: str, level: str, text: str, detail: str | None = None) -> dict:
    return {"name": name, "level": level, "text": text, "detail": detail}


def _size(path) -> int:
    try:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size
    except OSError:
        return 0


def _mb(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n < 1073741824 else f"{n / 1073741824:.2f} GB"


async def _ollama(conn: sqlite3.Connection) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(config.OLLAMA_URL + "/api/tags")
            r.raise_for_status()
            have = {m["name"] for m in r.json().get("models", [])}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return [_check("Ollama", "error", f"nicht erreichbar unter {config.OLLAMA_URL}", type(exc).__name__)]
    wanted = {config.OLLAMA_MODEL, config.OLLAMA_VISION_MODEL, config.OLLAMA_EMBED_MODEL}
    for col in ("ollama_model", "vision_model", "embed_model"):
        wanted |= {r[col] for r in conn.execute(f"SELECT DISTINCT {col} FROM user_settings WHERE {col} IS NOT NULL")}
    norm = lambda m: m if ":" in m else m + ":latest"  # noqa: E731
    missing = sorted(m for m in wanted if norm(m) not in {norm(h) for h in have})
    if missing:
        return [_check("Ollama", "warn", f"erreichbar, {len(have)} Modelle – es fehlen: {', '.join(missing)}",
                       "Laden mit: " + " · ".join(f"ollama pull {m}" for m in missing))]
    return [_check("Ollama", "ok", f"erreichbar, {len(have)} Modelle, alle benötigten vorhanden")]


async def _whisper() -> dict:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(config.WHISPER_HOST, config.WHISPER_PORT), 3)
    except (OSError, asyncio.TimeoutError):
        return _check("Whisper", "error", f"nicht erreichbar unter {config.WHISPER_HOST}:{config.WHISPER_PORT}")
    try:
        writer.write(b'{"type": "describe"}\n')
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), 3)
        kind = json.loads(line).get("type") if line else None
        return _check("Whisper", "ok" if kind == "info" else "warn",
                      "erreichbar (Wyoming)" if kind == "info" else "Port offen, aber keine Wyoming-Antwort")
    except (OSError, ValueError, asyncio.TimeoutError):
        return _check("Whisper", "warn", "Port offen, aber keine Wyoming-Antwort")
    finally:
        writer.close()


def _local_checks(conn: sqlite3.Connection, tz) -> list[dict]:
    out = []
    st = push.STATS
    subs = conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]
    level = "warn" if st["failed"] and st["last_error_at"] and st["last_error_at"] > (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ") else "ok"
    out.append(_check("Web-Push", level, f"{subs} Abos · seit Start {st['sent']} gesendet, {st['failed']} Fehler",
                      f"Letzter Fehler {st['last_error_at']}: {st['last_error']}" if st["last_error"] else None))
    total = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    online = sum(1 for d in conn.execute("SELECT id FROM devices") if events.has_subscribers("device", d["id"]))
    pending = conn.execute("SELECT COUNT(*) FROM device_messages WHERE delivered_at IS NULL").fetchone()[0]
    out.append(_check("Android-Geräte", "ok", f"{total} registriert, {online} online, {pending} Nachrichten warten"))
    mail_err = conn.execute("SELECT COUNT(*) FROM mail_accounts WHERE enabled = 1 AND last_error IS NOT NULL").fetchone()[0]
    mail_all = conn.execute("SELECT COUNT(*) FROM mail_accounts WHERE enabled = 1").fetchone()[0]
    out.append(_check("Mail-Abruf", "warn" if mail_err else "ok", f"{mail_all} Postfächer aktiv" + (f", {mail_err} mit Fehler" if mail_err else "")))
    ch_err = conn.execute("SELECT COUNT(*) FROM notify_channels WHERE enabled = 1 AND last_error IS NOT NULL").fetchone()[0]
    ch_all = conn.execute("SELECT COUNT(*) FROM notify_channels WHERE enabled = 1").fetchone()[0]
    out.append(_check("Benachrichtigungskanäle", "warn" if ch_err else "ok", f"{ch_all} aktiv" + (f", {ch_err} mit Fehler" if ch_err else "")
                      + (" · E-Mail-Versand eingerichtet" if config.SMTP_HOST else " · E-Mail-Versand nicht eingerichtet")))
    loop = st["loop_at"]
    stale = not loop or loop < (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    errs = st["job_errors"]
    out.append(_check("Hintergrundjobs", "error" if stale else "warn" if errs else "ok",
                      ("seit über 5 Minuten kein Lauf" if stale else "laufen jede Minute (Erinnerungen, Zusammenfassungen, Mail, Backup)")
                      + (f" · Fehler in: {', '.join(errs)}" if errs else ""),
                      "; ".join(f"{k}: {v['error']}" for k, v in errs.items()) or None))
    db_size = _size(config.DB_PATH) + _size(config.DB_PATH.with_name(config.DB_PATH.name + "-wal"))
    att = _size(config.DATA_DIR / "attachments")
    backups = sorted((config.DATA_DIR / "backups").glob("todo-*.db")) if (config.DATA_DIR / "backups").is_dir() else []
    disk = shutil.disk_usage(config.DATA_DIR)
    free_pct = disk.free / disk.total * 100 if disk.total else 100
    counts = {k: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for k, t in (("Benutzer", "users"), ("Aufgaben", "todos"), ("Anhänge", "attachments"))}
    out.append(_check("Datenbank", "ok", f"{_mb(db_size)} · " + " · ".join(f"{v} {k}" for k, v in counts.items()) + f" · Anhänge {_mb(att)}"))
    last = None
    if backups:  # Dateiname in UTC -> Ortszeit des Admins
        last = datetime.strptime(backups[-1].name[5:20], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).astimezone(tz)
    out.append(_check("Speicher", "error" if free_pct < 5 else "warn" if free_pct < 15 else "ok",
                      f"{_mb(disk.free)} frei von {_mb(disk.total)} ({free_pct:.0f} %)"
                      + (f" · letztes Backup {last:%d.%m. %H:%M}" if last else " · noch kein Backup")))
    problems = []
    if not config.PUBLIC_URL:
        problems.append("PUBLIC_URL nicht gesetzt (Links in Benachrichtigungen, Passkeys, Einladungen)")
    if not config.COOKIE_SECURE:
        problems.append("COOKIE_SECURE=false – nur für Tests ohne HTTPS")
    pending_users = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    out.append(_check("Konfiguration", "warn" if problems else "ok", "; ".join(problems) or
                      f"in Ordnung · SSO-Anbieter: {len(config.OIDC_PROVIDERS)}" + (f" · {pending_users} Benutzer warten auf Freigabe" if pending_users else "")))
    return out


@router.get("/status")
async def status(admin: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    ollama, whisper = await asyncio.gather(_ollama(conn), _whisper())
    checks = [*ollama, whisper, *_local_checks(conn, user_tz(conn, admin.id))]
    worst = "error" if any(c["level"] == "error" for c in checks) else "warn" if any(c["level"] == "warn" for c in checks) else "ok"
    return {"overall": worst, "checked_at": now(), "started_at": push.STATS["started_at"], "checks": checks}
