"""Single Sign-On über OpenID Connect (Authentik, Keycloak, Authelia, Google, ...): Authorization-Code-Flow mit PKCE.

Sicherheitsregeln:
- Identitäten werden nur über (Provider, sub) zugeordnet - nie automatisch per E-Mail/Benutzername mit einem
  bestehenden Konto verknüpft (Konto-Übernahme). Verknüpfen geht nur bewusst aus den Einstellungen heraus.
- state (+ Cookie-Bindung), nonce und PKCE; das ID-Token wird per JWKS-Signatur, iss, aud, exp und nonce geprüft.
- Neue SSO-Benutzer sind wie bei der Registrierung "pending", außer der erste Benutzer überhaupt (Admin)
  oder der Anbieter ist mit auto_approve konfiguriert.
"""
import base64
import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import config, events, push
from .db import audit, get_db, now, tx
from .security import (SESSION_COOKIE, Auth, client_ip, create_session, enforce_rate, get_auth, hash_password)

log = logging.getLogger("todo.sso")
router = APIRouter(prefix="/api/auth", tags=["sso"])

STATE_COOKIE = "oidc_state"
STATE_TTL = 600
ASYMMETRIC = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"]
SYMMETRIC = ["HS256", "HS384", "HS512"]


class SsoError(Exception):
    """Interner Fehler - der Nutzer sieht nur eine allgemeine Meldung, Details stehen im Log."""


def _client() -> httpx.AsyncClient:  # in Tests ersetzbar
    return httpx.AsyncClient(timeout=15, follow_redirects=False)


# ------------------------------------------------------------------ Discovery & JWKS (Cache)
_cache: dict[str, tuple[float, dict]] = {}


async def _get_json(url: str, ttl: int = 3600, force: bool = False) -> dict:
    hit = _cache.get(url)
    if hit and not force and time.monotonic() - hit[0] < ttl:
        return hit[1]
    try:
        async with _client() as c:
            r = await c.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SsoError(f"GET {url} fehlgeschlagen: {exc}") from exc
    _cache[url] = (time.monotonic(), data)
    return data


async def discovery(p: dict) -> dict:
    doc = await _get_json(p["issuer"].rstrip("/") + "/.well-known/openid-configuration")
    if doc.get("issuer", "").rstrip("/") != p["issuer"].rstrip("/"):
        raise SsoError("Issuer der Discovery-Antwort stimmt nicht mit der Konfiguration überein.")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if key in doc and config.COOKIE_SECURE and not str(doc[key]).startswith("https://"):
            raise SsoError(f"Discovery-Feld {key} fehlt oder ist nicht https.")
        if key not in doc:
            raise SsoError(f"Discovery-Feld {key} fehlt.")
    return doc


async def _signing_key(p: dict, doc: dict, header: dict):
    alg, kid = header.get("alg"), header.get("kid")
    if alg in SYMMETRIC:
        if not p["client_secret"]:
            raise SsoError("HS*-signiertes Token, aber kein client_secret konfiguriert.")
        return p["client_secret"]
    if alg not in ASYMMETRIC:
        raise SsoError(f"Nicht erlaubter Signatur-Algorithmus: {alg}")
    for force in (False, True):  # bei unbekannter kid einmal neu laden (Key-Rotation)
        keys = (await _get_json(doc["jwks_uri"], ttl=3600, force=force)).get("keys", [])
        match = [k for k in keys if k.get("kid") == kid] if kid else (keys if len(keys) == 1 else [])
        if match:
            return jwt.PyJWK(match[0]).key
    raise SsoError("Signaturschlüssel (kid) nicht im JWKS gefunden.")


# ------------------------------------------------------------------ Hilfen
def _redirect_uri(request: Request, pid: str) -> str:
    base = config.PUBLIC_URL or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/oidc/{pid}/callback"


def _provider(pid: str) -> dict:
    p = config.OIDC_PROVIDERS.get(pid.lower())
    if p is None:
        raise HTTPException(404, "Unbekannter SSO-Anbieter.")
    return p


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _back(code: str) -> RedirectResponse:
    r = RedirectResponse(f"/?sso={code}", status_code=302)
    r.delete_cookie(STATE_COOKIE, path="/api/auth/oidc")
    return r


def _groups(claims: dict, claim: str) -> list[str]:
    v = claims.get(claim)
    if isinstance(v, str):
        return [v]
    return [g for g in v if isinstance(g, str)] if isinstance(v, list) else []


def _username(conn: sqlite3.Connection, claims: dict, p: dict) -> str:
    raw = str(claims.get(p["username_claim"]) or str(claims.get("email", "")).split("@")[0] or claims["sub"])
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:28].strip("._-") or "user"
    base = base.ljust(3, "_")
    name, n = base, 1
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
        n += 1
        name = f"{base}-{n}"
    return name


# ------------------------------------------------------------------ Öffentliche Infos
@router.get("/oidc/providers")
def providers():
    local = config.LOCAL_AUTH_ENABLED or not config.OIDC_PROVIDERS
    return {"providers": [{"id": p["id"], "name": p["name"]} for p in config.OIDC_PROVIDERS.values()],
            "local_auth": local}


# ------------------------------------------------------------------ Start des Flows
@router.get("/oidc/{pid}/login")
async def oidc_login(pid: str, request: Request, link: bool = False, conn: sqlite3.Connection = Depends(get_db)):
    p = _provider(pid)
    enforce_rate(f"sso-start:{client_ip(request)}", 30, 300)
    link_user_id = None
    if link:  # nur mit gültiger Sitzung (Navigation aus der App heraus, Cookie wird mitgesendet)
        link_user_id = get_auth(request, conn).id
    try:
        doc = await discovery(p)
    except SsoError as exc:
        log.warning("SSO-Discovery fehlgeschlagen: %s", exc)
        return _back("error")
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    conn.execute("DELETE FROM oidc_states WHERE created_at < ?",
                 ((datetime.now(timezone.utc) - timedelta(seconds=STATE_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
    conn.execute("INSERT INTO oidc_states (state, provider, nonce, verifier, link_user_id, created_at) VALUES (?,?,?,?,?,?)",
                 (state, p["id"], nonce, verifier, link_user_id, now()))
    qs = urlencode({"response_type": "code", "client_id": p["client_id"], "redirect_uri": _redirect_uri(request, p["id"]),
                    "scope": p["scopes"], "state": state, "nonce": nonce, "code_challenge": challenge,
                    "code_challenge_method": "S256"})
    resp = RedirectResponse(f"{doc['authorization_endpoint']}?{qs}", status_code=302)
    # Lax: der Rücksprung vom Anbieter ist eine Cross-Site-Navigation, Strict würde den Cookie nicht senden.
    resp.set_cookie(STATE_COOKIE, state, max_age=STATE_TTL, httponly=True, secure=config.COOKIE_SECURE,
                    samesite="lax", path="/api/auth/oidc")
    return resp


# ------------------------------------------------------------------ Rücksprung
async def _exchange(p: dict, doc: dict, code: str, verifier: str, redirect_uri: str) -> dict:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "code_verifier": verifier, "client_id": p["client_id"]}
    auth = None
    if p["client_secret"]:
        methods = doc.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
        if "client_secret_basic" in methods:
            auth = httpx.BasicAuth(p["client_id"], p["client_secret"])
        else:
            data["client_secret"] = p["client_secret"]
    try:
        async with _client() as c:
            r = await c.post(doc["token_endpoint"], data=data, auth=auth, headers={"Accept": "application/json"})
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SsoError(f"Token-Austausch fehlgeschlagen: {exc}") from exc


async def _claims(p: dict, doc: dict, tokens: dict, nonce: str) -> dict:
    id_token = tokens.get("id_token")
    if not id_token:
        raise SsoError("Antwort enthält kein id_token.")
    try:
        header = jwt.get_unverified_header(id_token)
        key = await _signing_key(p, doc, header)
        claims = jwt.decode(id_token, key, algorithms=[header["alg"]], audience=p["client_id"],
                            issuer=doc["issuer"], leeway=60, options={"require": ["exp", "iat", "sub", "iss", "aud"]})
    except jwt.PyJWTError as exc:
        raise SsoError(f"ID-Token ungültig: {exc}") from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SsoError("nonce stimmt nicht überein.")
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != p["client_id"]:
        raise SsoError("azp stimmt nicht mit client_id überein.")
    # Zusätzliche Claims (Gruppen, E-Mail) per userinfo ergänzen - best effort, nur mit passendem sub.
    if tokens.get("access_token") and doc.get("userinfo_endpoint"):
        try:
            async with _client() as c:
                r = await c.get(doc["userinfo_endpoint"], headers={"Authorization": f"Bearer {tokens['access_token']}"})
                info = r.json() if r.status_code == 200 else {}
            if info.get("sub") == claims["sub"]:
                claims = {**info, **claims}
        except (httpx.HTTPError, ValueError):
            pass
    return claims


def _finish_login(conn: sqlite3.Connection, request: Request, user_id: int) -> RedirectResponse:
    token, _ = create_session(conn, user_id, request.headers.get("user-agent"))
    resp = _back("ok")
    resp.set_cookie(SESSION_COOKIE, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                    secure=config.COOKIE_SECURE, samesite="strict", path="/")
    return resp


@router.get("/oidc/{pid}/callback")
async def oidc_callback(pid: str, request: Request, code: str | None = None, state: str | None = None,
                        error: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    p = _provider(pid)
    ip = client_ip(request)
    enforce_rate(f"sso-cb:{ip}", 30, 300)
    cookie = request.cookies.get(STATE_COOKIE, "")
    if error or not code or not state or not hmac.compare_digest(cookie, state):
        log.warning("SSO-Callback abgelehnt (error=%s, state_ok=%s)", error, bool(state) and cookie == state)
        audit(conn, "sso", "sso_rejected", f"{p['id']}: {error or 'state/code fehlt oder Cookie passt nicht'}", None, ip)
        return _back("error")
    row = conn.execute("SELECT * FROM oidc_states WHERE state = ?", (state,)).fetchone()
    conn.execute("DELETE FROM oidc_states WHERE state = ?", (state,))  # einmalig verwendbar
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=STATE_TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if row is None or row["provider"] != p["id"] or row["created_at"] < cutoff:
        return _back("error")
    try:
        doc = await discovery(p)
        tokens = await _exchange(p, doc, code, row["verifier"], _redirect_uri(request, p["id"]))
        claims = await _claims(p, doc, tokens, row["nonce"])
    except SsoError as exc:
        log.warning("SSO fehlgeschlagen: %s", exc)
        audit(conn, "sso", "sso_failed", f"{p['id']}: {str(exc)[:200]}", None, ip)
        return _back("error")

    sub, email = str(claims["sub"]), (str(claims["email"])[:200] if claims.get("email") else None)
    is_admin_group = bool(set(p["admin_groups"]) & set(_groups(claims, p["groups_claim"])))
    ident = conn.execute("SELECT * FROM identities WHERE provider = ? AND subject = ?", (p["id"], sub)).fetchone()

    # --- bewusstes Verknüpfen eines bestehenden Kontos
    if row["link_user_id"] is not None:
        if ident is not None and ident["user_id"] != row["link_user_id"]:
            return _back("link_taken")
        if ident is None:
            conn.execute("INSERT INTO identities (user_id, provider, subject, email, created_at) VALUES (?,?,?,?,?)",
                         (row["link_user_id"], p["id"], sub, email, now()))
            audit(conn, "sso", "sso_link", p["id"], row["link_user_id"], ip)
        return _back("linked")

    pending_new = None
    if ident is None:
        with tx(conn):
            if conn.execute("SELECT 1 FROM identities WHERE provider = ? AND subject = ?", (p["id"], sub)).fetchone():
                return _back("error")
            first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            approved = first or p["auto_approve"]
            role = "admin" if first or (is_admin_group and approved) else "user"
            username = _username(conn, claims, p)
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, has_password, role, status, created_at, approved_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (username, hash_password(secrets.token_urlsafe(32)), 0, role, "approved" if approved else "pending",
                 now(), now() if approved else None))
            user_id = cur.lastrowid
            conn.execute("INSERT INTO identities (user_id, provider, subject, email, created_at) VALUES (?,?,?,?,?)",
                         (user_id, p["id"], sub, email, now()))
            audit(conn, username, "sso_register", f"{p['id']} role={role} approved={approved}", user_id, ip)
            if not approved:
                pending_new = username
    else:
        user_id = ident["user_id"]

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if pending_new:
        admins = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role='admin' AND status='approved'")]
        for a in admins:
            events.publish("user", a, "admin", {"op": "pending_user", "username": pending_new})
        push.notify_threadsafe(admins, "Neue Registrierung", f"{pending_new} (SSO) wartet auf Freigabe.", "/#admin")
    if user["status"] == "pending":
        return _back("pending")
    if user["status"] != "approved":
        return _back("denied")
    if is_admin_group and user["role"] != "admin":  # nur hochstufen, nie automatisch herabstufen
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
    conn.execute("UPDATE identities SET last_login_at = ?, email = COALESCE(?, email) WHERE provider = ? AND subject = ?",
                 (now(), email, p["id"], sub))
    audit(conn, user["username"], "sso_login", p["id"], user_id, ip)
    return _finish_login(conn, request, user_id)


# ------------------------------------------------------------------ Verknüpfte Anmeldungen
@router.get("/identities")
def list_identities(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, provider, email, created_at, last_login_at FROM identities WHERE user_id = ? ORDER BY id",
                        (auth.id,))
    out = []
    for r in rows:
        d = dict(r)
        d["provider_name"] = config.OIDC_PROVIDERS.get(r["provider"], {}).get("name", r["provider"])
        out.append(d)
    return {"identities": out, "has_password": bool(auth.user["has_password"])}


@router.delete("/identities/{identity_id}", status_code=204)
def unlink_identity(identity_id: int, request: Request, auth: Auth = Depends(get_auth),
                    conn: sqlite3.Connection = Depends(get_db)):
    if not auth.user["has_password"]:
        others = conn.execute("SELECT COUNT(*) FROM identities WHERE user_id = ? AND id != ?", (auth.id, identity_id)).fetchone()[0]
        if others == 0:
            raise HTTPException(422, "Setze zuerst ein Passwort, sonst kannst du dich nicht mehr anmelden.")
    cur = conn.execute("DELETE FROM identities WHERE id = ? AND user_id = ?", (identity_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Verknüpfung nicht gefunden.")
    audit(conn, auth.user["username"], "sso_unlink", str(identity_id), auth.id, client_ip(request))
