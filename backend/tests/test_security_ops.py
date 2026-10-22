import base64
import json
import time

import pytest

from app import backup, db, mfa
from tests.conftest import login, make_user


def test_totp_rfc6238_vector():
    secret = b"12345678901234567890"
    assert mfa.totp_now(secret, at=59) == "287082"          # RFC 6238 (8 Stellen: 94287082)
    assert mfa.totp_now(secret, at=1111111109) == "081804"


@pytest.fixture()
def alice(client):
    make_user(client, "alice")
    login(client, "alice")
    return client


def enable_2fa(c):
    s = c.post("/api/auth/2fa/setup").json()
    assert s["uri"].startswith("otpauth://totp/Todo%3Aalice?secret=") and s["qr_svg"].startswith("data:image/svg+xml;base64,")
    secret = base64.b32decode(s["secret"])
    r = c.post("/api/auth/2fa/enable", json={"code": mfa.totp_now(secret)})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"]


def fresh_code(secret):
    # nächster Zeitschritt: der aktuelle ist nach dem Aktivieren bereits verbraucht
    return mfa.totp_now(secret, at=time.time() + 30)


def test_2fa_setup_login_and_replay(alice):
    assert alice.post("/api/auth/2fa/enable", json={"code": "123456"}).status_code == 409  # ohne Einrichtung
    secret, codes = enable_2fa(alice)
    assert len(codes) == 10 and alice.get("/api/auth/2fa").json() == {"enabled": True, "recovery_left": 10}
    with db.session() as c:
        enc = c.execute("SELECT totp_secret_enc FROM users").fetchone()["totp_secret_enc"]
    assert base64.b32encode(secret).decode() not in enc  # verschlüsselt
    alice.cookies.clear(); alice.headers.pop("X-CSRF-Token")
    r = alice.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).json()
    assert r["twofa_required"] and "csrf" not in r
    assert alice.get("/api/auth/me").status_code == 401  # noch keine Sitzung
    assert alice.post("/api/auth/login/2fa", json={"ticket": r["ticket"], "code": "000000"}).status_code == 401
    code = fresh_code(secret)
    ok = alice.post("/api/auth/login/2fa", json={"ticket": r["ticket"], "code": code})
    assert ok.status_code == 200 and ok.json()["user"]["twofa"] is True
    assert alice.get("/api/auth/me").status_code == 200
    # gleicher Code ein zweites Mal -> abgelehnt (Replay)
    alice.cookies.clear()
    r2 = alice.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).json()
    assert alice.post("/api/auth/login/2fa", json={"ticket": r2["ticket"], "code": code}).status_code == 401
    # Ticket ist nur einmal verwendbar
    assert alice.post("/api/auth/login/2fa", json={"ticket": r["ticket"], "code": fresh_code(secret)}).status_code == 401


def test_recovery_code_single_use_and_ticket_attempts(alice):
    secret, codes = enable_2fa(alice)
    alice.cookies.clear(); alice.headers.pop("X-CSRF-Token")
    t = alice.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).json()["ticket"]
    r = alice.post("/api/auth/login/2fa", json={"ticket": t, "code": codes[0].upper()})
    assert r.status_code == 200 and r.json()["used_recovery"] and r.json()["recovery_left"] == 9
    alice.cookies.clear()
    t = alice.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).json()["ticket"]
    assert alice.post("/api/auth/login/2fa", json={"ticket": t, "code": codes[0]}).status_code == 401  # verbraucht
    for _ in range(4):
        alice.post("/api/auth/login/2fa", json={"ticket": t, "code": "999999"})
    assert alice.post("/api/auth/login/2fa", json={"ticket": t, "code": codes[1]}).status_code == 401  # Ticket gesperrt


def test_2fa_disable_requires_code(alice):
    secret, codes = enable_2fa(alice)
    assert alice.post("/api/auth/2fa/disable", json={"code": "123456"}).status_code == 403
    assert alice.post("/api/auth/2fa/disable", json={"code": codes[3]}).json() == {"enabled": False}
    alice.cookies.clear(); alice.headers.pop("X-CSRF-Token")
    assert "csrf" in alice.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).json()


def test_enabling_2fa_logs_out_other_sessions(client):
    make_user(client, "alice")
    other = client.__class__(client.app)
    login(other, "alice")
    login(client, "alice")
    enable_2fa(client)
    assert other.get("/api/auth/me").status_code == 401 and client.get("/api/auth/me").status_code == 200


def test_sessions_list_and_revoke(client):
    make_user(client, "alice")
    other = client.__class__(client.app)
    login(other, "alice")
    login(client, "alice")
    sessions = client.get("/api/auth/sessions").json()["sessions"]
    assert len(sessions) == 3 and sum(s["current"] for s in sessions) == 1  # Registrierung + 2 Logins
    current = next(s for s in sessions if s["current"])
    assert client.delete(f"/api/auth/sessions/{current['id']}").status_code == 422
    assert client.delete("/api/auth/sessions/zzzz").status_code == 422
    target = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/auth/sessions/{target['id']}").status_code == 204
    client.post("/api/auth/sessions/revoke-others")
    assert other.get("/api/auth/me").status_code == 401
    assert [s["current"] for s in client.get("/api/auth/sessions").json()["sessions"]] == [True]


def test_passkey_endpoints_reject_bad_input(alice):
    opts = alice.post("/api/auth/passkeys/register/options").json()
    assert opts["rp"]["id"] == "testserver" and opts["user"]["name"] == "alice" and opts["challenge"]
    r = alice.post("/api/auth/passkeys/register/verify", json={"name": "x", "credential": {"id": "abc", "response": {}}})
    assert r.status_code == 400
    # Challenge ist verbraucht
    r = alice.post("/api/auth/passkeys/register/verify", json={"name": "x", "credential": {}})
    assert r.status_code == 400
    anon = alice.__class__(alice.app)
    lo = anon.post("/api/auth/passkeys/login/options", json={}).json()
    assert lo["rpId"] == "testserver" and lo.get("allowCredentials", []) == []
    assert anon.post("/api/auth/passkeys/login/verify", json={"credential": {"id": "unbekannt"}}).status_code == 401
    assert anon.post("/api/auth/passkeys/login/verify", json={"credential": {"id": "x"}}).status_code == 400  # ohne Challenge
    assert alice.get("/api/auth/passkeys").json() == {"passkeys": []}


def test_backup_and_retention(alice, monkeypatch):
    alice.post("/api/todos", json={"title": "Sichern"})
    monkeypatch.setattr(backup, "KEEP", 2)
    names = []
    for i in range(3):
        names.append(alice.post("/api/admin/backups").json()["name"])
        time.sleep(1.05)
    listed = [b["name"] for b in alice.get("/api/admin/backups").json()["backups"]]
    assert listed == names[:0:-1]  # die zwei neuesten
    import sqlite3
    from app import config
    con = sqlite3.connect(config.DATA_DIR / "backups" / listed[0])
    assert con.execute("SELECT title FROM todos").fetchall() == [("Sichern",)]
    con.close()
    assert alice.get(f"/api/admin/backups/{listed[0]}").status_code == 200
    assert alice.get("/api/admin/backups/..%2Ftodo.db").status_code == 404
    with db.session() as c:
        c.execute("DELETE FROM settings WHERE key = 'last_backup'")
    backup.daily_backup(); backup.daily_backup()  # nur einmal pro Tag


def test_backups_admin_only(client):
    make_user(client, "alice")
    client.cookies.clear()
    make_user(client, "bob")
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username='bob'")
    login(client, "bob")
    assert client.get("/api/admin/backups").status_code == 403
    assert client.post("/api/admin/backups").status_code == 403


def test_export_json_and_csv(alice):
    alice.post("/api/todos", json={"title": "=HYPERLINK(\"http://evil\")", "tags": ["x"]})
    alice.post("/api/agent-bus/agents", json={"name": "ci"})
    data = alice.get("/api/export?format=json")
    assert "attachment" in data.headers["content-disposition"]
    j = data.json()
    assert j["format"] == "todo-export/1" and j["todos"][0]["tags"] == ["x"] and j["agents"][0]["name"] == "ci"
    assert "key_hash" not in json.dumps(j) and "password" not in json.dumps(j)
    csv = alice.get("/api/export?format=csv").text
    assert "'=HYPERLINK" in csv and csv.startswith("﻿id;titel")
    assert alice.get("/api/export?format=xml").status_code == 422
