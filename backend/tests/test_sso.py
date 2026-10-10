import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config, sso
from tests.conftest import login, make_user

ISSUER = "https://idp.test/application/o/todo/"
CLIENT_ID = "todo-client"


class FakeIdp:
    """Minimaler OIDC-Anbieter (Discovery, JWKS, Token, Userinfo) mit echten RS256-Signaturen."""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict = {}
        self.userinfo: dict = {}
        self.nonce = ""
        self.sign_with = self.key
        self.audience = CLIENT_ID
        self.token_requests: list[dict] = []

    def jwks(self):
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid="k1", use="sig", alg="RS256")
        return {"keys": [jwk]}

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "issuer": ISSUER, "authorization_endpoint": "https://idp.test/application/o/authorize/",
                "token_endpoint": "https://idp.test/application/o/token/", "jwks_uri": "https://idp.test/jwks/",
                "userinfo_endpoint": "https://idp.test/application/o/userinfo/",
                "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"]})
        if url == "https://idp.test/jwks/":
            return httpx.Response(200, json=self.jwks())
        if url == "https://idp.test/application/o/token/":
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            self.token_requests.append({"form": form, "auth": request.headers.get("authorization")})
            now = int(time.time())
            payload = {"iss": ISSUER, "aud": self.audience, "iat": now, "exp": now + 300, "nonce": self.nonce, **self.claims}
            token = jwt.encode(payload, self.sign_with, algorithm="RS256", headers={"kid": "k1"})
            return httpx.Response(200, json={"id_token": token, "access_token": "at", "token_type": "Bearer"})
        if url == "https://idp.test/application/o/userinfo/":
            return httpx.Response(200, json={"sub": self.claims["sub"], **self.userinfo})
        return httpx.Response(404)


@pytest.fixture()
def idp(client, monkeypatch):
    fake = FakeIdp()
    provider = {"id": "authentik", "name": "Authentik", "issuer": ISSUER, "client_id": CLIENT_ID,
                "client_secret": "s3cret", "scopes": "openid profile email", "username_claim": "preferred_username",
                "groups_claim": "groups", "admin_groups": ["todo-admins"], "auto_approve": False}
    monkeypatch.setattr(config, "OIDC_PROVIDERS", {"authentik": provider})
    monkeypatch.setattr(sso, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)))
    sso._cache.clear()
    fake.provider = provider
    return fake


def start(client, link=False):
    r = client.get("/api/auth/oidc/authentik/login" + ("?link=1" if link else ""), follow_redirects=False)
    assert r.status_code == 302, r.text
    return r.headers["location"], {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}


def sso_login(client, idp, sub="u1", name="anna", link=False, nonce=None, **extra):
    loc, q = start(client, link)
    idp.nonce = nonce if nonce is not None else q["nonce"]
    idp.claims = {"sub": sub, "preferred_username": name, "email": f"{name}@example.com", **extra}
    r = client.get(f"/api/auth/oidc/authentik/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert r.status_code == 302
    return r.headers["location"]


def test_providers_public_without_secret(client, idp):
    r = client.get("/api/auth/oidc/providers")
    assert r.json() == {"providers": [{"id": "authentik", "name": "Authentik"}], "local_auth": True}


def test_authorization_request_uses_pkce_state_nonce(client, idp):
    loc, q = start(client)
    assert loc.startswith("https://idp.test/application/o/authorize/?")
    assert q["response_type"] == "code" and q["client_id"] == CLIENT_ID and q["code_challenge_method"] == "S256"
    assert q["redirect_uri"].endswith("/api/auth/oidc/authentik/callback")
    assert len(q["state"]) > 20 and len(q["nonce"]) > 20 and len(q["code_challenge"]) > 20
    assert "oidc_state" in client.cookies


def test_first_sso_user_is_admin(client, idp):
    assert sso_login(client, idp) == "/?sso=ok"
    me = client.get("/api/auth/me").json()
    assert me["user"]["role"] == "admin" and me["user"]["username"] == "anna" and me["user"]["has_password"] is False
    # PKCE-Verifier und Client-Secret wurden beim Token-Austausch gesendet
    req = idp.token_requests[0]
    assert "code_verifier" in req["form"] and req["auth"].startswith("Basic ")


def test_second_user_pending_until_approved(client, idp):
    sso_login(client, idp, sub="admin", name="boss")
    client.cookies.clear()
    assert sso_login(client, idp, sub="u2", name="bob") == "/?sso=pending"
    assert client.get("/api/auth/me").status_code == 401
    # Admin gibt frei
    client.cookies.clear()
    sso_login(client, idp, sub="admin", name="boss")
    login_headers = {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf"]}
    bob = next(u for u in client.get("/api/admin/users").json()["users"] if u["username"] == "bob")
    assert client.post(f"/api/admin/users/{bob['id']}/approve", headers=login_headers).status_code == 200
    client.cookies.clear()
    assert sso_login(client, idp, sub="u2", name="bob") == "/?sso=ok"
    assert client.get("/api/auth/me").json()["user"]["username"] == "bob"
    assert client.get("/api/admin/users").status_code == 403  # Bob ist normaler Benutzer, kein Admin


def test_no_automatic_linking_by_username(client, idp):
    make_user(client, "alice")  # lokaler Admin "alice"
    client.cookies.clear()
    assert sso_login(client, idp, sub="evil", name="alice") == "/?sso=pending"
    from app import db
    with db.session() as c:
        names = sorted(r["username"] for r in c.execute("SELECT username FROM users"))
        assert names == ["alice", "alice-2"]  # neues, getrenntes Konto - keine Übernahme von "alice"
        assert c.execute("SELECT user_id FROM identities").fetchone()["user_id"] != 1


def test_admin_group_and_auto_approve(client, idp):
    make_user(client, "root")
    client.cookies.clear()
    idp.provider["auto_approve"] = True
    assert sso_login(client, idp, sub="g1", name="chef", groups=["todo-admins"]) == "/?sso=ok"
    assert client.get("/api/auth/me").json()["user"]["role"] == "admin"
    client.cookies.clear()
    assert sso_login(client, idp, sub="g2", name="normal", groups=["staff"]) == "/?sso=ok"
    assert client.get("/api/auth/me").json()["user"]["role"] == "user"


def test_groups_from_userinfo(client, idp):
    make_user(client, "root")
    client.cookies.clear()
    idp.provider["auto_approve"] = True
    idp.userinfo = {"groups": ["todo-admins"]}
    assert sso_login(client, idp, sub="g3", name="viaui") == "/?sso=ok"
    assert client.get("/api/auth/me").json()["user"]["role"] == "admin"


def test_blocked_user_denied(client, idp):
    sso_login(client, idp, sub="adm", name="boss")
    client.cookies.clear()
    idp.provider["auto_approve"] = True
    sso_login(client, idp, sub="u9", name="eve")
    from app import db
    with db.session() as c:
        c.execute("UPDATE users SET status='blocked' WHERE username='eve'")
    client.cookies.clear()
    assert sso_login(client, idp, sub="u9", name="eve") == "/?sso=denied"
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("case", ["bad_nonce", "wrong_audience", "wrong_signature", "no_cookie", "bad_state", "replay"])
def test_rejects_invalid_responses(client, idp, case):
    loc, q = start(client)
    idp.nonce = "falsch" if case == "bad_nonce" else q["nonce"]
    idp.audience = "anderer-client" if case == "wrong_audience" else CLIENT_ID
    idp.sign_with = idp.other_key if case == "wrong_signature" else idp.key
    idp.claims = {"sub": "x", "preferred_username": "mallory"}
    state = "gefaelscht" if case == "bad_state" else q["state"]
    if case == "no_cookie":
        client.cookies.clear()
    url = f"/api/auth/oidc/authentik/callback?code=abc&state={state}"
    r = client.get(url, follow_redirects=False)
    if case == "replay":
        assert r.headers["location"] == "/?sso=pending" or r.headers["location"] == "/?sso=ok"
        client.cookies.set("oidc_state", q["state"], path="/api/auth/oidc")
        r = client.get(url, follow_redirects=False)  # zweite Verwendung desselben state
    assert r.headers["location"] == "/?sso=error"
    from app import db
    with db.session() as c:
        if case != "replay":
            assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_provider_error_param_and_unknown_provider(client, idp):
    r = client.get("/api/auth/oidc/authentik/callback?error=access_denied&state=x", follow_redirects=False)
    assert r.headers["location"] == "/?sso=error"
    assert client.get("/api/auth/oidc/nope/login", follow_redirects=False).status_code == 404


def test_link_and_unlink_flow(client, idp):
    make_user(client, "alice")
    login(client, "alice")
    assert sso_login(client, idp, sub="L1", name="alice-sso", link=True) == "/?sso=linked"
    ids = client.get("/api/auth/identities").json()
    assert len(ids["identities"]) == 1 and ids["has_password"] is True
    ident_id = ids["identities"][0]["id"]
    # ab jetzt kann man sich mit SSO in dasselbe Konto einloggen
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    assert sso_login(client, idp, sub="L1", name="whatever") == "/?sso=ok"
    assert client.get("/api/auth/me").json()["user"]["username"] == "alice"
    client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
    assert client.delete(f"/api/auth/identities/{ident_id}").status_code == 204
    assert client.get("/api/auth/identities").json()["identities"] == []


def test_link_requires_session_and_unique_identity(client, idp):
    r = client.get("/api/auth/oidc/authentik/login?link=1", follow_redirects=False)
    assert r.status_code == 401
    make_user(client, "alice")
    login(client, "alice")
    sso_login(client, idp, sub="L2", name="a", link=True)
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    from app import db
    make_user(client, "bob")
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username='bob'")
    login(client, "bob")
    assert sso_login(client, idp, sub="L2", name="b", link=True) == "/?sso=link_taken"


def test_sso_only_user_cannot_unlink_until_password_set(client, idp):
    sso_login(client, idp, sub="S1", name="solo")
    client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
    ident_id = client.get("/api/auth/identities").json()["identities"][0]["id"]
    assert client.delete(f"/api/auth/identities/{ident_id}").status_code == 422
    r = client.post("/api/auth/password", json={"new_password": "ein-langes-passwort"})  # ohne aktuelles Passwort
    assert r.status_code == 204
    assert client.get("/api/auth/me").json()["user"]["has_password"] is True
    assert client.delete(f"/api/auth/identities/{ident_id}").status_code == 204
    # SSO-Konten ohne Passwort können sich nicht per Passwort anmelden (Hash ist zufällig)
    client.cookies.clear()


def test_sso_account_has_no_usable_password(client, idp):
    sso_login(client, idp, sub="S2", name="nopw")
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"username": "nopw", "password": "irgendwas"})
    assert r.status_code == 401


def test_local_auth_can_be_disabled(client, idp, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_AUTH_ENABLED", False)
    assert client.get("/api/auth/oidc/providers").json()["local_auth"] is False
    assert client.post("/api/auth/login", json={"username": "a", "password": "b"}).status_code == 403
    assert client.post("/api/auth/register", json={"username": "abc", "password": "passwort-12345"}).status_code == 403
    assert sso_login(client, idp, sub="S3", name="ssoonly") == "/?sso=ok"


def test_local_auth_flag_ignored_without_providers(client, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_AUTH_ENABLED", False)
    monkeypatch.setattr(config, "OIDC_PROVIDERS", {})
    assert client.get("/api/auth/oidc/providers").json() == {"providers": [], "local_auth": True}
    assert make_user(client, "alice")["admin"] is True


def test_provider_config_loading(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.example.com/application/o/todo/")
    monkeypatch.setenv("OIDC_CLIENT_ID", "cid")
    monkeypatch.setenv("OIDC_ADMIN_GROUPS", "a, b")
    p = config.load_oidc_providers()["authentik"]
    assert p["name"] == "Authentik" and p["admin_groups"] == ["a", "b"] and p["scopes"] == "openid profile email"
    monkeypatch.setenv("OIDC_PROVIDERS", json.dumps([
        {"id": "kc", "name": "Keycloak", "issuer": "https://kc/realms/x", "client_id": "c"},
        {"id": "google", "issuer": "https://accounts.google.com", "client_id": "g", "client_secret": "z"}]))
    assert set(config.load_oidc_providers()) == {"kc", "google"}
    monkeypatch.setenv("OIDC_PROVIDERS", json.dumps([{"id": "bad id!", "issuer": "x", "client_id": "y"}]))
    with pytest.raises(ValueError):
        config.load_oidc_providers()
