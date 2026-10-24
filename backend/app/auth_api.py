import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import config, events, push
from .db import audit, get_db, now, tx
from .security import (SESSION_COOKIE, Auth, client_ip, create_session, enforce_rate, get_auth, hash_password,
                       limiter, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])
_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RegisterIn(Credentials):
    password: str = Field(min_length=10, max_length=256)
    invite: str | None = Field(default=None, max_length=100)  # Einladungslink: sofort freigegeben

    @field_validator("username")
    @classmethod
    def _valid(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME.match(v):
            raise ValueError("Benutzername: 3-32 Zeichen (Buchstaben, Ziffern, _ . -).")
        return v


class PasswordChange(BaseModel):
    current_password: str = Field(default="", max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                        secure=config.COOKIE_SECURE, samesite="strict", path="/")


def user_public(u: sqlite3.Row) -> dict:
    return {"id": u["id"], "username": u["username"], "role": u["role"], "status": u["status"],
            "has_password": bool(u["has_password"]), "twofa": bool(u["totp_secret_enc"])}


def _require_local_auth() -> None:
    if not config.LOCAL_AUTH_ENABLED and config.OIDC_PROVIDERS:
        raise HTTPException(403, "Die Anmeldung mit Passwort ist deaktiviert. Bitte Single Sign-On verwenden.")


@router.post("/register", status_code=201)
def register(data: RegisterIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    _require_local_auth()
    ip = client_ip(request)
    enforce_rate(f"register:{ip}", 5, 3600)
    pw_hash = hash_password(data.password)
    with tx(conn):
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (data.username,)).fetchone():
            raise HTTPException(409, "Benutzername bereits vergeben.")
        first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        invited = None
        if data.invite and not first:
            from .invites import consume

            invited = consume(conn, data.invite)
        role, status = ("admin", "approved") if first else ("user", "approved" if invited else "pending")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, status, created_at, approved_at) VALUES (?,?,?,?,?,?)",
            (data.username, pw_hash, role, status, now(), now() if status == "approved" else None),
        )
        user_id = cur.lastrowid
        audit(conn, data.username, "register", f"role={role} status={status}" + (f" invite={invited['id']}" if invited else ""), user_id, ip)
    if invited:
        token, _ = create_session(conn, user_id, request.headers.get("user-agent"), client_ip(request))
        _set_cookie(response, token)
        admins = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role='admin' AND status='approved'")]
        push.notify_threadsafe(admins, "Neues Mitglied", f"{data.username} hat sich per Einladung registriert.", "/#/admin")
        return {"status": "approved", "admin": False}
    if first:
        token, _ = create_session(conn, user_id, request.headers.get("user-agent"), client_ip(request))
        _set_cookie(response, token)
        return {"status": "approved", "admin": True}
    admins = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role='admin' AND status='approved'")]
    for a in admins:
        events.publish("user", a, "admin", {"op": "pending_user", "username": data.username})
    push.notify_threadsafe(admins, "Neue Registrierung", f"{data.username} wartet auf Freigabe.", "/#admin")
    return {"status": "pending", "admin": False}


@router.post("/login")
def login(data: Credentials, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    _require_local_auth()
    ip = client_ip(request)
    ukey = f"login-user:{data.username.lower()}"
    ikey = f"login-ip:{ip}"
    window, limit = config.LOGIN_WINDOW_SECONDS, config.LOGIN_MAX_FAILURES
    if limiter.blocked(ukey, limit, window) or limiter.blocked(ikey, limit * 4, window):
        raise HTTPException(429, "Zu viele Fehlversuche. Bitte später erneut versuchen.")
    user = conn.execute("SELECT * FROM users WHERE username = ?", (data.username,)).fetchone()
    if not verify_password(user["password_hash"] if user else None, data.password):
        limiter.hit(ukey, window)
        limiter.hit(ikey, window)
        audit(conn, data.username, "login_failed", None, user["id"] if user else None, ip)
        raise HTTPException(401, "Benutzername oder Passwort falsch.")
    limiter.reset(ukey)
    if user["status"] == "pending":
        raise HTTPException(403, "Dein Konto wartet noch auf die Freigabe durch einen Administrator.")
    if user["status"] != "approved":
        raise HTTPException(403, "Dein Konto wurde abgelehnt oder gesperrt.")
    if user["totp_secret_enc"]:  # zweiter Faktor nötig: noch keine Sitzung, nur ein kurzlebiges Ticket
        from .mfa import create_ticket

        return {"twofa_required": True, "ticket": create_ticket(conn, user["id"])}
    token, csrf = create_session(conn, user["id"], request.headers.get("user-agent"), client_ip(request))
    audit(conn, user["username"], "login", None, user["id"], ip)
    _set_cookie(response, token)
    return {"user": user_public(user), "csrf": csrf}


@router.post("/logout", status_code=204)
def logout(response: Response, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (auth.token_hash,))
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(auth: Auth = Depends(get_auth)):
    return {"user": user_public(auth.user), "csrf": auth.csrf}


@router.post("/password", status_code=204)
def change_password(data: PasswordChange, request: Request, auth: Auth = Depends(get_auth),
                    conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"pwchange:{auth.id}", 5, 900)
    if auth.user["has_password"] and not verify_password(auth.user["password_hash"], data.current_password):
        raise HTTPException(403, "Aktuelles Passwort falsch.")
    conn.execute("UPDATE users SET password_hash = ?, has_password = 1 WHERE id = ?",
                 (hash_password(data.new_password), auth.id))
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (auth.id, auth.token_hash))
    audit(conn, auth.user["username"], "password_change", None, auth.id, client_ip(request))


# ------------------------------------------------------------------ Angemeldete Geräte (Sitzungen)
@router.get("/sessions")
def list_sessions(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM sessions WHERE user_id = ? AND expires_at > ? ORDER BY COALESCE(last_seen_at, created_at) DESC",
                        (auth.id, now()))
    return {"sessions": [{"id": r["token_hash"][:16], "created_at": r["created_at"], "last_seen_at": r["last_seen_at"],
                          "user_agent": r["user_agent"], "ip": r["ip"], "current": r["token_hash"] == auth.token_hash} for r in rows]}


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if not re.fullmatch(r"[0-9a-f]{16}", session_id) or auth.token_hash.startswith(session_id):
        raise HTTPException(422, "Die aktuelle Sitzung bitte über „Abmelden“ beenden.")
    cur = conn.execute("DELETE FROM sessions WHERE user_id = ? AND substr(token_hash, 1, 16) = ?", (auth.id, session_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Sitzung nicht gefunden.")
    audit(conn, auth.user["username"], "session_revoke", session_id, auth.id, client_ip(request))


@router.post("/sessions/revoke-others", status_code=204)
def revoke_others(request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (auth.id, auth.token_hash))
    audit(conn, auth.user["username"], "session_revoke_others", None, auth.id, client_ip(request))


# ------------------------------------------------------------------ Login-Warnung bei neuem Gerät
class AlertsIn(BaseModel):
    enabled: bool


@router.get("/login-alerts")
def login_alerts(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT login_alerts FROM user_settings WHERE user_id = ?", (auth.id,)).fetchone()
    devices = conn.execute("SELECT fingerprint, label, first_seen_at, last_seen_at, last_ip FROM known_devices WHERE user_id = ? "
                           "ORDER BY last_seen_at DESC", (auth.id,))
    return {"enabled": bool(row["login_alerts"]) if row else True,
            "devices": [{**dict(d), "id": d["fingerprint"][:16]} for d in devices]}


@router.put("/login-alerts")
def set_login_alerts(data: AlertsIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (auth.id,))
    conn.execute("UPDATE user_settings SET login_alerts = ? WHERE user_id = ?", (int(data.enabled), auth.id))
    return {"enabled": data.enabled}


@router.delete("/known-devices/{fid}", status_code=204)
def forget_device(fid: str, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Gerät vergessen: die nächste Anmeldung damit löst wieder eine Warnung aus."""
    if len(fid) != 16 or conn.execute("DELETE FROM known_devices WHERE user_id = ? AND substr(fingerprint, 1, 16) = ?",
                                      (auth.id, fid)).rowcount == 0:
        raise HTTPException(404, "Gerät nicht gefunden.")
