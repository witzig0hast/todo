"""Weitere Benachrichtigungskanäle pro Benutzer: ntfy, Gotify, Telegram, Matrix, E-Mail. Alles, was über Web-Push und die
Android-App geht, kann zusätzlich (oder nur bei dringenden Meldungen) hierhin. Zugangsdaten liegen verschlüsselt in /data."""
import ipaddress
import json
import logging
import secrets
import smtplib
import socket
import sqlite3
import ssl
from email.message import EmailMessage
from typing import Literal
from urllib.parse import quote, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config
from .db import get_db, now
from .mailin import _crypto
from .security import Auth, enforce_rate, get_auth

log = logging.getLogger("todo.channels")
router = APIRouter(prefix="/api/channels", tags=["channels"])
MAX_CHANNELS = 10
TIMEOUT = 10


class ChannelIn(BaseModel):
    kind: Literal["ntfy", "gotify", "telegram", "matrix", "email"]
    name: str = Field(default="", max_length=40)
    urgent_only: bool = False
    # je nach Art: url (ntfy/gotify/matrix-Homeserver), topic, token, chat_id, room, to
    url: str = Field(default="", max_length=300)
    topic: str = Field(default="", max_length=100)
    token: str = Field(default="", max_length=500)
    chat_id: str = Field(default="", max_length=60)
    room: str = Field(default="", max_length=200)
    to: str = Field(default="", max_length=200)


class ChannelPatch(BaseModel):
    enabled: bool | None = None
    urgent_only: bool | None = None


def _host_allowed(url: str, is_admin: bool) -> None:
    """Keine Anfragen ins interne Netz über fremde Konten (SSRF), außer es ist ausdrücklich erlaubt."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(422, "Adresse muss mit http:// oder https:// beginnen.")
    policy = config.NOTIFY_PRIVATE_HOSTS
    if policy == "true" or (policy == "admins" and is_admin):
        return
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except OSError as exc:
        raise HTTPException(422, f"Server „{parts.hostname}“ nicht gefunden.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(422, "Server im internen Netz sind für dein Konto nicht erlaubt (Admin: NOTIFY_PRIVATE_HOSTS).")


def _validate(data: ChannelIn, is_admin: bool) -> dict:
    c = data.model_dump(exclude={"name", "urgent_only", "kind"})
    k = data.kind
    if k == "ntfy":
        c["url"] = (c["url"] or "https://ntfy.sh").rstrip("/")
        if not c["topic"] or not all(ch.isalnum() or ch in "-_" for ch in c["topic"]):
            raise HTTPException(422, "ntfy: Thema (Topic) fehlt oder enthält ungültige Zeichen.")
    elif k == "gotify":
        if not c["url"] or not c["token"]:
            raise HTTPException(422, "Gotify: Server-Adresse und App-Token angeben.")
    elif k == "telegram":
        if not c["token"] or ":" not in c["token"] or not c["chat_id"]:
            raise HTTPException(422, "Telegram: Bot-Token (von @BotFather) und Chat-ID angeben.")
    elif k == "matrix":
        if not c["url"] or not c["token"] or not c["room"].startswith("!"):
            raise HTTPException(422, "Matrix: Homeserver, Access-Token und Raum-ID (!…:server) angeben.")
    elif k == "email":
        if not config.SMTP_HOST:
            raise HTTPException(422, "E-Mail-Versand ist auf dem Server nicht eingerichtet (SMTP_HOST).")
        if "@" not in c["to"] or len(c["to"]) < 5:
            raise HTTPException(422, "E-Mail: gültige Empfängeradresse angeben.")
    if k in ("ntfy", "gotify", "matrix"):
        c["url"] = c["url"].rstrip("/")
        _host_allowed(c["url"], is_admin)
    return {key: v for key, v in c.items() if v}


def _out(r: sqlite3.Row) -> dict:
    cfg = json.loads(_crypto().decrypt(r["config_enc"].encode()))
    hint = {"ntfy": f"{cfg.get('url')}/{cfg.get('topic')}", "gotify": cfg.get("url"), "telegram": f"Chat {cfg.get('chat_id')}",
            "matrix": cfg.get("room"), "email": cfg.get("to")}.get(r["kind"], "")
    return {"id": r["id"], "kind": r["kind"], "name": r["name"], "enabled": bool(r["enabled"]), "urgent_only": bool(r["urgent_only"]),
            "target": hint, "last_error": r["last_error"], "last_sent_at": r["last_sent_at"]}


# ------------------------------------------------------------------ Versand
def _send_one(kind: str, cfg: dict, title: str, body: str, url: str | None, urgent: bool) -> None:
    link = (config.PUBLIC_URL + url) if url and url.startswith("/") and config.PUBLIC_URL else None
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as client:
        if kind == "ntfy":  # JSON-Veröffentlichung: Umlaute im Titel ohne Header-Kodierung
            r = client.post(cfg["url"], json={"topic": cfg["topic"], "title": title, "message": body or title,
                                              "priority": 4 if urgent else 3, "tags": ["white_check_mark"],
                                              **({"click": link} if link else {})},
                            headers={"Authorization": "Bearer " + cfg["token"]} if cfg.get("token") else {})
        elif kind == "gotify":
            r = client.post(cfg["url"] + "/message", params={"token": cfg["token"]},
                            json={"title": title, "message": body or title, "priority": 8 if urgent else 5})
        elif kind == "telegram":
            text = f"*{title}*\n{body}" if body else f"*{title}*"
            r = client.post(f"https://api.telegram.org/bot{cfg['token']}/sendMessage",
                            json={"chat_id": cfg["chat_id"], "text": text + (f"\n{link}" if link else ""), "parse_mode": "Markdown",
                                  "disable_notification": False})
        elif kind == "matrix":
            txn = secrets.token_hex(8)
            r = client.put(f"{cfg['url']}/_matrix/client/v3/rooms/{quote(cfg['room'], safe='')}/send/m.room.message/{txn}",
                           headers={"Authorization": "Bearer " + cfg["token"]},
                           json={"msgtype": "m.text", "body": f"{title}\n{body}".strip()})
        elif kind == "email":
            send_mail(cfg["to"], title, (body or title) + (f"\n\n{link}" if link else ""))
            return
        else:
            return
        if r.status_code >= 300:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")


def send_mail(to: str, subject: str, text: str) -> None:
    if not config.SMTP_HOST:
        raise RuntimeError("SMTP nicht eingerichtet.")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM or config.SMTP_USER, to, subject[:200]
    msg.set_content(text)
    ctx = ssl.create_default_context()
    if config.SMTP_TLS == "ssl":
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=TIMEOUT, context=ctx)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=TIMEOUT)
    with server:
        if config.SMTP_TLS == "starttls":
            server.starttls(context=ctx)
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)


def deliver(conn: sqlite3.Connection, user_ids: list[int], payload: dict) -> None:
    """Aus push._send_sync (Hintergrund-Thread): an alle aktiven Kanäle der Benutzer."""
    if not user_ids:
        return
    marks = ",".join("?" * len(user_ids))
    urgent = bool(payload.get("urgent"))
    rows = conn.execute(f"SELECT c.*, u.role FROM notify_channels c JOIN users u ON u.id = c.user_id "
                        f"WHERE c.enabled = 1 AND c.user_id IN ({marks})", user_ids).fetchall()
    for r in rows:
        if r["urgent_only"] and not urgent:
            continue
        try:
            cfg = json.loads(_crypto().decrypt(r["config_enc"].encode()))
            if r["kind"] in ("ntfy", "gotify", "matrix"):
                _host_allowed(cfg["url"], r["role"] == "admin")  # erneut prüfen (DNS kann sich ändern)
            _send_one(r["kind"], cfg, str(payload.get("title") or "Todo")[:200], str(payload.get("body") or "")[:1000],
                      payload.get("url"), urgent)
            conn.execute("UPDATE notify_channels SET last_sent_at = ?, last_error = NULL WHERE id = ?", (now(), r["id"]))
        except Exception as exc:  # ein kaputter Kanal darf nichts anderes stören
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            log.warning("Kanal %s/%s fehlgeschlagen: %s", r["kind"], r["id"], detail)
            conn.execute("UPDATE notify_channels SET last_error = ? WHERE id = ?", (str(detail)[:300], r["id"]))


# ------------------------------------------------------------------ Endpunkte
@router.get("")
def list_channels(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM notify_channels WHERE user_id = ? ORDER BY id", (auth.id,))
    return {"channels": [_out(r) for r in rows], "email_available": bool(config.SMTP_HOST)}


@router.post("", status_code=201)
def add_channel(data: ChannelIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM notify_channels WHERE user_id = ?", (auth.id,)).fetchone()[0] >= MAX_CHANNELS:
        raise HTTPException(422, f"Maximal {MAX_CHANNELS} Kanäle.")
    cfg = _validate(data, auth.is_admin)
    cur = conn.execute("INSERT INTO notify_channels (user_id, kind, name, config_enc, urgent_only, created_at) VALUES (?,?,?,?,?,?)",
                       (auth.id, data.kind, data.name.strip(), _crypto().encrypt(json.dumps(cfg).encode()).decode(),
                        int(data.urgent_only), now()))
    return _out(conn.execute("SELECT * FROM notify_channels WHERE id = ?", (cur.lastrowid,)).fetchone())


def _own(conn: sqlite3.Connection, user_id: int, cid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM notify_channels WHERE id = ? AND user_id = ?", (cid, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Kanal nicht gefunden.")
    return row


@router.patch("/{cid}")
def patch_channel(cid: int, data: ChannelPatch, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _own(conn, auth.id, cid)
    for key, val in data.model_dump(exclude_none=True).items():
        conn.execute(f"UPDATE notify_channels SET {key} = ? WHERE id = ?", (int(val), cid))
    return _out(_own(conn, auth.id, cid))


@router.delete("/{cid}", status_code=204)
def delete_channel(cid: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _own(conn, auth.id, cid)
    conn.execute("DELETE FROM notify_channels WHERE id = ?", (cid,))


@router.post("/{cid}/test")
def test_channel(cid: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"channel-test:{auth.id}", 10, 60)
    row = _own(conn, auth.id, cid)
    cfg = json.loads(_crypto().decrypt(row["config_enc"].encode()))
    try:
        if row["kind"] in ("ntfy", "gotify", "matrix"):
            _host_allowed(cfg["url"], auth.is_admin)
        _send_one(row["kind"], cfg, "Todo: Test", "Wenn du das liest, funktioniert der Kanal.", "/#/settings", False)
    except HTTPException:
        raise
    except Exception as exc:
        conn.execute("UPDATE notify_channels SET last_error = ? WHERE id = ?", (str(exc)[:300], cid))
        raise HTTPException(502, f"Senden fehlgeschlagen: {str(exc)[:200]}") from exc
    conn.execute("UPDATE notify_channels SET last_sent_at = ?, last_error = NULL WHERE id = ?", (now(), cid))
    return {"ok": True}

