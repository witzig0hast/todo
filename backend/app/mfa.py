"""Zwei-Faktor-Anmeldung (TOTP, RFC 6238) mit Wiederherstellungscodes.

Ablauf: Passwort korrekt + 2FA aktiv -> kurzlebiges Login-Ticket (kein Cookie) -> Code eingeben -> Sitzung.
Das TOTP-Geheimnis liegt verschlüsselt in der DB; jeder Code gilt nur einmal (letzter Zeitschritt wird gemerkt).
"""
import base64
import hashlib
import hmac
import io
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .db import audit, get_db, now
from .mailin import _crypto
from .security import Auth, client_ip, create_session, enforce_rate, get_auth, sha256

router = APIRouter(prefix="/api/auth", tags=["2fa"])
STEP = 30
TICKET_TTL = 300
TICKET_ATTEMPTS = 5
RECOVERY_COUNT = 10


def _hotp(secret: bytes, counter: int) -> str:
    digest = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def totp_now(secret: bytes, at: float | None = None) -> str:
    return _hotp(secret, int((at or time.time()) // STEP))


def _verify_totp(secret: bytes, code: str, last_step: int, at: float | None = None) -> int | None:
    """Gibt den Zeitschritt zurück, wenn der Code gültig ist (±1 Schritt Toleranz) und noch nicht benutzt wurde."""
    code = code.strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        return None
    current = int((at or time.time()) // STEP)
    for step in (current - 1, current, current + 1):
        if step > last_step and hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def _secret_of(enc: str) -> bytes:
    return base64.b32decode(_crypto().decrypt(enc.encode()).decode())


def _normalize_recovery(code: str) -> str:
    return code.strip().lower().replace("-", "").replace(" ", "")


def _new_recovery_codes(conn: sqlite3.Connection, user_id: int) -> list[str]:
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    codes = []
    for _ in range(RECOVERY_COUNT):
        raw = secrets.token_hex(4) + secrets.token_hex(4)
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}")
        conn.execute("INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, ?)", (user_id, sha256(_normalize_recovery(raw))))
    return codes


def check_second_factor(conn: sqlite3.Connection, user: sqlite3.Row, code: str) -> str | None:
    """Prüft TOTP-Code oder Wiederherstellungscode. Gibt 'totp'/'recovery' zurück oder None."""
    if not user["totp_secret_enc"]:
        return None
    step = _verify_totp(_secret_of(user["totp_secret_enc"]), code, user["totp_last_step"] or 0)
    if step is not None:
        conn.execute("UPDATE users SET totp_last_step = ? WHERE id = ?", (step, user["id"]))
        return "totp"
    row = conn.execute("SELECT id FROM recovery_codes WHERE user_id = ? AND code_hash = ? AND used_at IS NULL",
                       (user["id"], sha256(_normalize_recovery(code)))).fetchone()
    if row:
        conn.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?", (now(), row["id"]))
        return "recovery"
    return None


def create_ticket(conn: sqlite3.Connection, user_id: int) -> str:
    ticket = secrets.token_urlsafe(32)
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=TICKET_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("DELETE FROM login_tickets WHERE created_at < ?", (cutoff,))
    conn.execute("INSERT INTO login_tickets (ticket_hash, user_id, created_at) VALUES (?,?,?)", (sha256(ticket), user_id, now()))
    return ticket


# ------------------------------------------------------------------ Einrichtung
class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=40)


@router.get("/2fa")
def status(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    left = conn.execute("SELECT COUNT(*) FROM recovery_codes WHERE user_id = ? AND used_at IS NULL", (auth.id,)).fetchone()[0]
    return {"enabled": bool(auth.user["totp_secret_enc"]), "recovery_left": left}


@router.post("/2fa/setup")
def setup(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if auth.user["totp_secret_enc"]:
        raise HTTPException(409, "2FA ist bereits aktiv. Zum Neu-Einrichten zuerst ausschalten.")
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    conn.execute("UPDATE users SET totp_pending_enc = ? WHERE id = ?", (_crypto().encrypt(secret.encode()).decode(), auth.id))
    label = quote(f"Todo:{auth.user['username']}")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer=Todo&digits=6&period=30"
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, dark="#000000", light="#ffffff")
    return {"secret": secret, "uri": uri, "qr_svg": "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()}


@router.post("/2fa/enable")
def enable(data: CodeIn, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"2fa-enable:{auth.id}", 10, 300)
    if not auth.user["totp_pending_enc"]:
        raise HTTPException(409, "Bitte zuerst die Einrichtung starten.")
    step = _verify_totp(_secret_of(auth.user["totp_pending_enc"]), data.code, 0)
    if step is None:
        raise HTTPException(422, "Code stimmt nicht. Uhrzeit des Handys prüfen und erneut versuchen.")
    conn.execute("UPDATE users SET totp_secret_enc = totp_pending_enc, totp_pending_enc = NULL, totp_last_step = ? WHERE id = ?",
                 (step, auth.id))
    codes = _new_recovery_codes(conn, auth.id)
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (auth.id, auth.token_hash))
    audit(conn, auth.user["username"], "2fa_enable", None, auth.id, client_ip(request))
    return {"enabled": True, "recovery_codes": codes}


@router.post("/2fa/disable")
def disable(data: CodeIn, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"2fa-disable:{auth.id}", 10, 300)
    if check_second_factor(conn, auth.user, data.code) is None:
        raise HTTPException(403, "Code ungültig.")
    conn.execute("UPDATE users SET totp_secret_enc = NULL, totp_pending_enc = NULL WHERE id = ?", (auth.id,))
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (auth.id,))
    audit(conn, auth.user["username"], "2fa_disable", None, auth.id, client_ip(request))
    return {"enabled": False}


@router.post("/2fa/recovery")
def regenerate(data: CodeIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"2fa-regen:{auth.id}", 5, 300)
    if check_second_factor(conn, auth.user, data.code) is None:
        raise HTTPException(403, "Code ungültig.")
    return {"recovery_codes": _new_recovery_codes(conn, auth.id)}


# ------------------------------------------------------------------ Anmeldung, zweiter Schritt
class TicketIn(BaseModel):
    ticket: str = Field(min_length=10, max_length=100)
    code: str = Field(min_length=6, max_length=40)


@router.post("/login/2fa")
def login_second_step(data: TicketIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    from .auth_api import _set_cookie, user_public

    ip = client_ip(request)
    enforce_rate(f"2fa-login:{ip}", 20, 300)
    t = conn.execute("SELECT * FROM login_tickets WHERE ticket_hash = ?", (sha256(data.ticket),)).fetchone()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=TICKET_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if t is None or t["created_at"] < cutoff or t["attempts"] >= TICKET_ATTEMPTS:
        raise HTTPException(401, "Anmeldung abgelaufen. Bitte erneut mit Passwort anmelden.")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (t["user_id"],)).fetchone()
    kind = check_second_factor(conn, user, data.code) if user and user["status"] == "approved" else None
    if kind is None:
        conn.execute("UPDATE login_tickets SET attempts = attempts + 1 WHERE ticket_hash = ?", (t["ticket_hash"],))
        audit(conn, user["username"] if user else "?", "2fa_failed", None, t["user_id"], ip)
        raise HTTPException(401, "Code ungültig.")
    conn.execute("DELETE FROM login_tickets WHERE ticket_hash = ?", (t["ticket_hash"],))
    token, csrf = create_session(conn, user["id"], request.headers.get("user-agent"))
    audit(conn, user["username"], "login", f"2fa:{kind}", user["id"], ip)
    _set_cookie(response, token)
    left = conn.execute("SELECT COUNT(*) FROM recovery_codes WHERE user_id = ? AND used_at IS NULL", (user["id"],)).fetchone()[0]
    return {"user": user_public(user), "csrf": csrf, "recovery_left": left, "used_recovery": kind == "recovery"}
