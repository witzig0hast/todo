import hashlib
import hmac
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request

from . import config
from .db import get_db, now

_ph = PasswordHasher()
# Gültiger Hash, gegen den bei unbekanntem Benutzer verglichen wird (gleiche Laufzeit).
_DUMMY_HASH = _ph.hash("dummy-password-for-timing")

SESSION_COOKIE = "session"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(stored: str | None, pw: str) -> bool:
    try:
        return _ph.verify(stored or _DUMMY_HASH, pw) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- Rate-Limiting
class RateLimiter:
    """Einfaches In-Memory-Fenster (ein Worker-Prozess)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, window: int) -> deque[float]:
        q = self._hits[key]
        cutoff = time.monotonic() - window
        while q and q[0] < cutoff:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
            q = self._hits[key]
        return q

    def blocked(self, key: str, limit: int, window: int) -> bool:
        return len(self._prune(key, window)) >= limit

    def hit(self, key: str, window: int) -> None:
        self._prune(key, window).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def clear(self) -> None:
        self._hits.clear()


limiter = RateLimiter()


def enforce_rate(key: str, limit: int, window: int) -> None:
    if limiter.blocked(key, limit, window):
        raise HTTPException(429, "Zu viele Versuche. Bitte später erneut versuchen.")
    limiter.hit(key, window)


# ---------------------------------------------------------------- Sessions
def create_session(conn: sqlite3.Connection, user_id: int, user_agent: str | None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, csrf, created_at, expires_at, user_agent) VALUES (?,?,?,?,?,?)",
        (sha256(token), user_id, csrf, now(), expires, (user_agent or "")[:200]),
    )
    return token, csrf


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True  # nicht-Browser-Clients; der CSRF-Token wird trotzdem geprüft
    host = request.headers.get("host", "")
    return urlsplit(origin).netloc == host


class Auth:
    """Aufgelöste Cookie-Sitzung."""

    def __init__(self, user: sqlite3.Row, csrf: str, token_hash: str) -> None:
        self.user = user
        self.csrf = csrf
        self.token_hash = token_hash

    @property
    def id(self) -> int:
        return self.user["id"]

    @property
    def is_admin(self) -> bool:
        return self.user["role"] == "admin"


def get_auth(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> Auth:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Nicht angemeldet.")
    row = conn.execute(
        "SELECT s.csrf, s.token_hash, s.expires_at, u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ?",
        (sha256(token),),
    ).fetchone()
    if row is None or row["expires_at"] < now():
        raise HTTPException(401, "Sitzung abgelaufen.")
    if row["status"] != "approved":
        raise HTTPException(403, "Konto nicht freigegeben.")
    if request.method in UNSAFE:
        sent = request.headers.get("x-csrf-token", "")
        if not _origin_ok(request) or not hmac.compare_digest(sent, row["csrf"]):
            raise HTTPException(403, "CSRF-Prüfung fehlgeschlagen.")
    return Auth(row, row["csrf"], row["token_hash"])


def require_admin(auth: Auth = Depends(get_auth)) -> Auth:
    if not auth.is_admin:
        raise HTTPException(403, "Nur für Administratoren.")
    return auth


# ---------------------------------------------------------------- Agent-Keys
def new_agent_key() -> tuple[str, str, str]:
    raw = "tdo_" + secrets.token_urlsafe(32)
    return raw, sha256(raw), raw[:10]


def get_agent(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row:
    key = request.headers.get("x-agent-key")
    if not key:
        raise HTTPException(401, "X-Agent-Key fehlt.")
    row = conn.execute(
        "SELECT a.*, u.status AS user_status FROM agents a JOIN users u ON u.id = a.user_id WHERE a.key_hash = ?",
        (sha256(key),),
    ).fetchone()
    if row is None or row["user_status"] != "approved":
        raise HTTPException(401, "Ungültiger Agent-Key.")
    conn.execute("UPDATE agents SET last_seen_at = ? WHERE id = ?", (now(), row["id"]))
    return row
