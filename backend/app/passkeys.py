"""Passkeys (WebAuthn): Anmelden per Fingerabdruck/Gesicht/Geräte-PIN ohne Passwort.

Registrieren nur mit angemeldeter Sitzung; Anmelden über eine einmalige Challenge (an den Browser gebunden).
RP-ID/Origin kommen aus PUBLIC_URL (hinter Proxy) bzw. der Anfrage.
"""
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from webauthn import (base64url_to_bytes, generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers import exceptions as wa_exc
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from . import config
from .db import audit, get_db, now
from .security import Auth, client_ip, create_session, enforce_rate, get_auth

router = APIRouter(prefix="/api/auth/passkeys", tags=["passkeys"])
# alle Fehlerklassen der Bibliothek (ungültige Antworten, kaputtes JSON/CBOR, ...) -> 400/401 statt 500
WA_ERRORS = tuple(v for v in vars(wa_exc).values() if isinstance(v, type) and issubclass(v, Exception)) + (ValueError, KeyError, TypeError)
CHALLENGE_TTL = 300
COOKIE = "wa_chal"


def _rp(request: Request) -> tuple[str, str]:
    base = config.PUBLIC_URL or str(request.base_url).rstrip("/")
    parts = urlsplit(base)
    return parts.hostname or "localhost", f"{parts.scheme}://{parts.netloc}"


def _store_challenge(conn: sqlite3.Connection, kind: str, challenge: bytes, user_id: int | None) -> str:
    cid = secrets.token_urlsafe(24)
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=CHALLENGE_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("DELETE FROM webauthn_challenges WHERE created_at < ?", (cutoff,))
    conn.execute("INSERT INTO webauthn_challenges (id, user_id, kind, challenge, created_at) VALUES (?,?,?,?,?)",
                 (cid, user_id, kind, bytes_to_base64url(challenge), now()))
    return cid


def _take_challenge(conn: sqlite3.Connection, cid: str | None, kind: str, user_id: int | None) -> bytes:
    row = conn.execute("SELECT * FROM webauthn_challenges WHERE id = ? AND kind = ?", (cid or "", kind)).fetchone() if cid else None
    conn.execute("DELETE FROM webauthn_challenges WHERE id = ?", (cid or "",))  # einmalig
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=CHALLENGE_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if row is None or row["created_at"] < cutoff or (user_id is not None and row["user_id"] != user_id):
        raise HTTPException(400, "Anfrage abgelaufen. Bitte erneut versuchen.")
    return base64url_to_bytes(row["challenge"])


def _set_chal_cookie(response: Response, cid: str) -> None:
    response.set_cookie(COOKIE, cid, max_age=CHALLENGE_TTL, httponly=True, secure=config.COOKIE_SECURE,
                        samesite="strict", path="/api/auth/passkeys")


class NameIn(BaseModel):
    name: str = Field(default="Passkey", min_length=1, max_length=60)
    credential: dict


class LoginOptionsIn(BaseModel):
    username: str | None = Field(default=None, max_length=64)


class LoginIn(BaseModel):
    credential: dict


# ------------------------------------------------------------------ Verwaltung
@router.get("")
def list_passkeys(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, name, created_at, last_used_at FROM passkeys WHERE user_id = ? ORDER BY id", (auth.id,))
    return {"passkeys": [dict(r) for r in rows]}


@router.delete("/{passkey_id}", status_code=204)
def delete_passkey(passkey_id: int, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("DELETE FROM passkeys WHERE id = ? AND user_id = ?", (passkey_id, auth.id)).rowcount == 0:
        raise HTTPException(404, "Passkey nicht gefunden.")
    audit(conn, auth.user["username"], "passkey_delete", str(passkey_id), auth.id, client_ip(request))


@router.post("/register/options")
def register_options(request: Request, response: Response, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"pk-reg:{auth.id}", 20, 300)
    rp_id, _ = _rp(request)
    existing = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"]))
                for r in conn.execute("SELECT credential_id FROM passkeys WHERE user_id = ?", (auth.id,))]
    opts = generate_registration_options(
        rp_id=rp_id, rp_name="Todo", user_name=auth.user["username"], user_id=f"todo-user-{auth.id}".encode(),
        exclude_credentials=existing,
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.PREFERRED,
                                                               user_verification=UserVerificationRequirement.PREFERRED))
    _set_chal_cookie(response, _store_challenge(conn, "reg", opts.challenge, auth.id))
    return json.loads(options_to_json(opts))


@router.post("/register/verify", status_code=201)
def register_verify(data: NameIn, request: Request, response: Response, auth: Auth = Depends(get_auth),
                    conn: sqlite3.Connection = Depends(get_db)):
    rp_id, origin = _rp(request)
    challenge = _take_challenge(conn, request.cookies.get(COOKIE), "reg", auth.id)
    response.delete_cookie(COOKIE, path="/api/auth/passkeys")
    try:
        v = verify_registration_response(credential=data.credential, expected_challenge=challenge,
                                         expected_rp_id=rp_id, expected_origin=origin)
    except WA_ERRORS as exc:
        raise HTTPException(400, "Passkey konnte nicht geprüft werden.") from exc
    if conn.execute("SELECT COUNT(*) FROM passkeys WHERE user_id = ?", (auth.id,)).fetchone()[0] >= 10:
        raise HTTPException(422, "Maximal 10 Passkeys.")
    transports = data.credential.get("response", {}).get("transports") or []
    conn.execute("INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, transports, name, created_at) VALUES (?,?,?,?,?,?,?)",
                 (auth.id, bytes_to_base64url(v.credential_id), v.credential_public_key, v.sign_count,
                  json.dumps(transports if isinstance(transports, list) else []), data.name.strip(), now()))
    audit(conn, auth.user["username"], "passkey_add", data.name.strip(), auth.id, client_ip(request))
    return {"ok": True}


# ------------------------------------------------------------------ Anmelden
@router.post("/login/options")
def login_options(data: LoginOptionsIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"pk-login:{client_ip(request)}", 30, 300)
    rp_id, _ = _rp(request)
    allow = None
    if data.username:  # sonst: auffindbare Passkeys (Browser bietet die passenden an)
        allow = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"]))
                 for r in conn.execute("SELECT p.credential_id FROM passkeys p JOIN users u ON u.id = p.user_id WHERE u.username = ?",
                                       (data.username.strip(),))]
    opts = generate_authentication_options(rp_id=rp_id, allow_credentials=allow or None,
                                           user_verification=UserVerificationRequirement.PREFERRED)
    _set_chal_cookie(response, _store_challenge(conn, "auth", opts.challenge, None))
    return json.loads(options_to_json(opts))


@router.post("/login/verify")
def login_verify(data: LoginIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    from .auth_api import _require_local_auth, _set_cookie, user_public

    _require_local_auth()
    ip = client_ip(request)
    enforce_rate(f"pk-login:{ip}", 30, 300)
    rp_id, origin = _rp(request)
    challenge = _take_challenge(conn, request.cookies.get(COOKIE), "auth", None)
    response.delete_cookie(COOKIE, path="/api/auth/passkeys")
    cred_id = str(data.credential.get("id") or data.credential.get("rawId") or "")
    pk = conn.execute("SELECT * FROM passkeys WHERE credential_id = ?", (cred_id,)).fetchone()
    if pk is None:
        raise HTTPException(401, "Unbekannter Passkey.")
    try:
        v = verify_authentication_response(credential=data.credential, expected_challenge=challenge, expected_rp_id=rp_id,
                                           expected_origin=origin, credential_public_key=pk["public_key"],
                                           credential_current_sign_count=pk["sign_count"])
    except WA_ERRORS as exc:
        audit(conn, "passkey", "passkey_failed", str(pk["id"]), pk["user_id"], ip)
        raise HTTPException(401, "Passkey-Anmeldung fehlgeschlagen.") from exc
    user = conn.execute("SELECT * FROM users WHERE id = ?", (pk["user_id"],)).fetchone()
    if user["status"] != "approved":
        raise HTTPException(403, "Dein Konto ist nicht freigegeben oder gesperrt.")
    conn.execute("UPDATE passkeys SET sign_count = ?, last_used_at = ? WHERE id = ?", (v.new_sign_count, now(), pk["id"]))
    token, csrf = create_session(conn, user["id"], request.headers.get("user-agent"), client_ip(request))
    audit(conn, user["username"], "login", "passkey", user["id"], ip)
    _set_cookie(response, token)
    return {"user": user_public(user), "csrf": csrf}
