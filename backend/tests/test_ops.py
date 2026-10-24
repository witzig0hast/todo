"""Paket 12: Statusseite für Admins, Warnung bei Anmeldung von neuem Gerät."""
import pytest

from app import push
from tests.conftest import login, make_user
from tests.test_planning import approve

CHROME_LINUX = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
FIREFOX_ANDROID = "Mozilla/5.0 (Android 14; Mobile; rv:131.0) Gecko/131.0 Firefox/131.0"


@pytest.fixture()
def alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(push, "notify_payload_threadsafe", lambda users, payload: sent.append((users, payload)))
    return sent


def relogin(client, ua, name="anna"):
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers["User-Agent"] = ua
    return login(client, name)


def test_login_alert_only_for_new_devices(client, alerts):
    client.headers["User-Agent"] = CHROME_LINUX
    make_user(client, "anna")                 # erste Sitzung (Registrierung) merkt sich das Gerät still
    relogin(client, CHROME_LINUX)
    assert alerts == []
    relogin(client, FIREFOX_ANDROID)          # neues Gerät -> Warnung (dringend, auch an „nur dringend“-Kanäle)
    assert len(alerts) == 1 and alerts[0][1]["title"] == "Neue Anmeldung bei Todo" and alerts[0][1]["urgent"]
    assert "Firefox · Android" in alerts[0][1]["body"]
    relogin(client, FIREFOX_ANDROID)          # jetzt bekannt
    assert len(alerts) == 1
    info = client.get("/api/auth/login-alerts").json()
    assert info["enabled"] is True and {d["label"] for d in info["devices"]} == {"Chrome · Linux", "Firefox · Android"}
    fid = [d["id"] for d in info["devices"] if d["label"] == "Firefox · Android"][0]
    assert client.delete(f"/api/auth/known-devices/{fid}").status_code == 204
    client.put("/api/auth/login-alerts", json={"enabled": False})
    relogin(client, FIREFOX_ANDROID)          # vergessen, aber Warnungen aus
    assert len(alerts) == 1
    audit = client.get("/api/admin/audit").json()["entries"]
    assert any(e["action"] == "login_new_device" for e in audit)


def test_existing_users_get_no_alert_after_update(client, alerts):
    """Nach dem Update kennt das System noch kein Gerät: die erste Anmeldung warnt nicht."""
    make_user(client, "anna")
    from app import db
    with db.session() as c:
        c.execute("DELETE FROM known_devices")
    relogin(client, FIREFOX_ANDROID)
    assert alerts == []


def test_status_page(client, monkeypatch):
    make_user(client, "admin")
    client.cookies.clear()
    make_user(client, "bob")
    approve("bob")
    login(client, "admin")
    r = client.get("/api/admin/status").json()
    names = [c["name"] for c in r["checks"]]
    assert names[:2] == ["Ollama", "Whisper"] and {"Web-Push", "Datenbank", "Speicher", "Hintergrundjobs", "Konfiguration"} <= set(names)
    assert r["overall"] in ("ok", "warn", "error")
    assert {c["name"]: c["level"] for c in r["checks"]}["Ollama"] == "error"  # im Test nicht erreichbar
    assert "COOKIE_SECURE" in {c["name"]: c["text"] for c in r["checks"]}["Konfiguration"]
    client.post("/api/auth/logout")
    client.cookies.clear()
    login(client, "bob")
    assert client.get("/api/admin/status").status_code == 403
