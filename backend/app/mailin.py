"""Mail -> Aufgabe: ein IMAP-Postfach pro Benutzer wird alle 2 Minuten auf ungelesene Mails geprüft.

- Nur Absender aus der Erlaubnisliste werden zu Aufgaben (Betreff = Titel, Text = Notizen, #tags im Betreff).
- Passwort verschlüsselt (Fernet, Schlüssel in DATA_DIR), nie an den Browser zurückgegeben.
- Nur IMAP über TLS (993) bzw. STARTTLS (143).
"""
import email
import email.policy
import imaplib
import logging
import re
import sqlite3
import ssl
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import config
from .db import get_db, now, session
from .security import Auth, enforce_rate, get_auth

log = logging.getLogger("todo.mail")
router = APIRouter(prefix="/api/mail", tags=["mail"])
POLL_SECONDS = 120
MAX_PER_RUN = 20
_fernet: Fernet | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_accounts (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  host TEXT NOT NULL, port INTEGER NOT NULL, username TEXT NOT NULL, password_enc TEXT NOT NULL,
  folder TEXT NOT NULL DEFAULT 'INBOX', allowed_senders TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  last_check_at TEXT, last_error TEXT, imported INTEGER NOT NULL DEFAULT 0
);
"""


def _crypto() -> Fernet:
    global _fernet
    if _fernet is None:
        path = config.DATA_DIR / "mail_key"
        if not path.exists():
            path.write_bytes(Fernet.generate_key())
            path.chmod(0o600)
        _fernet = Fernet(path.read_bytes())
    return _fernet


class MailConfig(BaseModel):
    host: str = Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9.-]+$")
    port: int = 993
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=500)  # None = unverändert lassen
    folder: str = Field(default="INBOX", min_length=1, max_length=100, pattern=r"^[^\r\n\"]+$")
    allowed_senders: list[str] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @field_validator("port")
    @classmethod
    def _port(cls, v: int) -> int:
        if v not in (993, 143):
            raise ValueError("Nur IMAP über TLS: Port 993 (oder 143 mit STARTTLS).")
        return v

    @field_validator("allowed_senders")
    @classmethod
    def _senders(cls, v: list[str]) -> list[str]:
        out = []
        for a in v:
            a = a.strip().lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", a):
                raise ValueError(f"Ungültige Absender-Adresse: {a}")
            out.append(a)
        return out


def _connect(host: str, port: int, username: str, password: str, folder: str) -> imaplib.IMAP4:
    ctx = ssl.create_default_context()
    if port == 993:
        imap: imaplib.IMAP4 = imaplib.IMAP4_SSL(host, port, ssl_context=ctx, timeout=20)
    else:
        imap = imaplib.IMAP4(host, port, timeout=20)
        imap.starttls(ssl_context=ctx)
    imap.login(username, password)
    typ, _ = imap.select(f'"{folder}"')
    if typ != "OK":
        imap.logout()
        raise imaplib.IMAP4.error("Ordner nicht gefunden")
    return imap


def _text_of(msg: email.message.EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        text = part.get_content()
    except (LookupError, ValueError):
        return ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()[:5000]


def import_message(conn: sqlite3.Connection, user_id: int, raw: bytes, allowed: set[str]) -> bool:
    from . import todos

    msg = email.message_from_bytes(raw, policy=email.policy.default)
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    if sender not in allowed:
        return False
    subject = str(msg.get("Subject", "") or "").strip()
    tags = [m.lower() for m in re.findall(r"(?:^|\s)#([\wäöüß-]{1,30})", subject)][:9]
    title = re.sub(r"(?:^|\s)#[\wäöüß-]{1,30}", " ", subject)
    title = re.sub(r"^(re|aw|fwd?|wg):\s*", "", re.sub(r"\s+", " ", title).strip(), flags=re.I)[:300] or "(ohne Betreff)"
    try:
        clean_tags = todos.normalize_tags(tags + ["mail"])
    except ValueError:
        clean_tags = ["mail"]
    todos.create_todo(conn, user_id, todos.TodoIn(title=title, notes=_text_of(msg), tags=clean_tags), created_by="mail")
    return True


def poll_account(conn: sqlite3.Connection, acc: sqlite3.Row) -> int:
    password = _crypto().decrypt(acc["password_enc"].encode()).decode()
    allowed = set(acc["allowed_senders"].split(","))
    imported = 0
    imap = _connect(acc["host"], acc["port"], acc["username"], password, acc["folder"])
    try:
        typ, data = imap.search(None, "UNSEEN")
        ids = (data[0].split() if typ == "OK" and data and data[0] else [])[:MAX_PER_RUN]
        for mid in ids:
            typ, parts = imap.fetch(mid, "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None) if typ == "OK" else None
            if raw and len(raw) <= 5 * 1024 * 1024 and import_message(conn, acc["user_id"], raw, allowed):
                imported += 1
            imap.store(mid, "+FLAGS", "\\Seen")  # auch nicht erlaubte Absender nicht erneut prüfen
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return imported


def poll_due_accounts() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=POLL_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with session() as conn:
        conn.executescript(SCHEMA)
        accounts = conn.execute("SELECT m.* FROM mail_accounts m JOIN users u ON u.id = m.user_id WHERE m.enabled = 1 "
                                "AND u.status = 'approved' AND (m.last_check_at IS NULL OR m.last_check_at < ?)", (cutoff,)).fetchall()
        for acc in accounts:
            error = None
            n = 0
            try:
                n = poll_account(conn, acc)
            except (imaplib.IMAP4.error, OSError, ssl.SSLError, InvalidToken) as exc:
                error = "Verbindung oder Anmeldung fehlgeschlagen"
                log.warning("IMAP für Benutzer %s: %s", acc["user_id"], exc)
            conn.execute("UPDATE mail_accounts SET last_check_at = ?, last_error = ?, imported = imported + ? WHERE user_id = ?",
                         (now(), error, n, acc["user_id"]))


# ------------------------------------------------------------------ API
def _out(r: sqlite3.Row | None) -> dict:
    if r is None:
        return {"configured": False}
    return {"configured": True, "host": r["host"], "port": r["port"], "username": r["username"], "folder": r["folder"],
            "allowed_senders": r["allowed_senders"].split(","), "enabled": bool(r["enabled"]),
            "last_check_at": r["last_check_at"], "last_error": r["last_error"], "imported": r["imported"]}


@router.get("")
def get_mail(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.executescript(SCHEMA)
    return _out(conn.execute("SELECT * FROM mail_accounts WHERE user_id = ?", (auth.id,)).fetchone())


@router.put("")
def put_mail(data: MailConfig, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.executescript(SCHEMA)
    existing = conn.execute("SELECT * FROM mail_accounts WHERE user_id = ?", (auth.id,)).fetchone()
    if data.password:
        enc = _crypto().encrypt(data.password.encode()).decode()
    elif existing:
        enc = existing["password_enc"]
    else:
        raise HTTPException(422, "Passwort fehlt.")
    conn.execute("INSERT INTO mail_accounts (user_id, host, port, username, password_enc, folder, allowed_senders, enabled) "
                 "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET host=excluded.host, port=excluded.port, "
                 "username=excluded.username, password_enc=excluded.password_enc, folder=excluded.folder, "
                 "allowed_senders=excluded.allowed_senders, enabled=excluded.enabled, last_check_at=NULL, last_error=NULL",
                 (auth.id, data.host, data.port, data.username, enc, data.folder, ",".join(data.allowed_senders), int(data.enabled)))
    return _out(conn.execute("SELECT * FROM mail_accounts WHERE user_id = ?", (auth.id,)).fetchone())


@router.delete("", status_code=204)
def delete_mail(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM mail_accounts WHERE user_id = ?", (auth.id,))


@router.post("/test")
def test_mail(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"mailtest:{auth.id}", 5, 300)
    conn.executescript(SCHEMA)
    acc = conn.execute("SELECT * FROM mail_accounts WHERE user_id = ?", (auth.id,)).fetchone()
    if acc is None:
        raise HTTPException(404, "Kein Postfach eingerichtet.")
    try:
        imap = _connect(acc["host"], acc["port"], acc["username"], _crypto().decrypt(acc["password_enc"].encode()).decode(), acc["folder"])
        typ, data = imap.search(None, "UNSEEN")
        unseen = len(data[0].split()) if typ == "OK" and data and data[0] else 0
        imap.logout()
    except (imaplib.IMAP4.error, OSError, ssl.SSLError, InvalidToken) as exc:
        log.info("IMAP-Test fehlgeschlagen: %s", exc)
        raise HTTPException(502, "Verbindung oder Anmeldung fehlgeschlagen. Server, Port, Benutzer und Passwort prüfen.") from exc
    return {"ok": True, "unseen": unseen}
