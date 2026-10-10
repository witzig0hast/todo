import pytest

from app import db, push
from tests.conftest import login, make_user


def reg(client, name="Pixel 8"):
    r = client.post("/api/devices/register", json={"name": name, "platform": "android", "app_version": "1.0"})
    assert r.status_code == 201, r.text
    return r.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def alice(client):
    make_user(client, "alice")
    login(client, "alice")
    return client


def test_register_returns_token_once_and_stores_hash(alice):
    d = reg(alice)
    assert d["token"].startswith("tdv_") and d["name"] == "Pixel 8"
    with db.session() as c:
        row = c.execute("SELECT * FROM devices").fetchone()
        assert row["token_hash"] != d["token"] and d["token"] not in str(dict(row))
    listed = alice.get("/api/devices").json()["devices"]
    assert len(listed) == 1 and "token" not in listed[0] and listed[0]["online"] is False and listed[0]["pending"] == 0


def test_register_requires_login_and_csrf(client):
    assert client.post("/api/devices/register", json={"name": "x"}).status_code == 401
    make_user(client, "alice")
    login(client, "alice")
    tok = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/devices/register", json={"name": "x"}).status_code == 403
    client.headers["X-CSRF-Token"] = tok


def test_duplicate_names_get_suffix(alice):
    assert reg(alice, "Pixel")["name"] == "Pixel"
    assert reg(alice, "pixel")["name"] == "pixel (2)"
    assert reg(alice, "Pixel")["name"] == "Pixel (3)"


def test_device_limit_and_registration_rate_limit(alice, monkeypatch):
    from app import devices
    monkeypatch.setattr(devices, "MAX_DEVICES", 2)
    reg(alice, "a")
    reg(alice, "b")
    assert alice.post("/api/devices/register", json={"name": "c"}).status_code == 422


def test_registration_rate_limit(alice):
    for i in range(10):
        reg(alice, f"d{i}")
    assert alice.post("/api/devices/register", json={"name": "elf"}).status_code in (422, 429)


def test_send_to_one_device_and_all(alice):
    a, b = reg(alice, "Phone"), reg(alice, "Tablet")
    r = alice.post("/api/devices/send", json={"device_id": a["id"], "title": "Hallo", "body": "Nur Phone", "url": "/#/today"})
    assert r.status_code == 200 and r.json()["sent"] == 1
    r = alice.post("/api/devices/send", json={"title": "An alle"})
    assert r.json()["sent"] == 2
    pend = {d["name"]: d["pending"] for d in alice.get("/api/devices").json()["devices"]}
    assert pend == {"Phone": 2, "Tablet": 1}


def test_send_validation(alice):
    d = reg(alice)
    assert alice.post("/api/devices/send", json={"device_id": d["id"], "title": ""}).status_code == 422
    for bad in ("https://evil.example", "//evil.example", "javascript:alert(1)", "/a b"):
        assert alice.post("/api/devices/send", json={"device_id": d["id"], "title": "x", "url": bad}).status_code == 422, bad
    assert alice.post("/api/devices/send", json={"device_id": 9999, "title": "x"}).status_code == 404


def test_send_without_devices(alice):
    assert alice.post("/api/devices/send", json={"title": "x"}).status_code == 404


def test_ack_and_isolation_between_devices(alice):
    a, b = reg(alice, "A"), reg(alice, "B")
    alice.post("/api/devices/send", json={"device_id": a["id"], "title": "für A"})
    with db.session() as c:
        mid = c.execute("SELECT id FROM device_messages").fetchone()["id"]
    assert alice.post(f"/api/devices/messages/{mid}/ack", headers=bearer(b["token"])).status_code == 404  # fremdes Gerät
    assert alice.post(f"/api/devices/messages/{mid}/ack", headers=bearer(a["token"])).status_code == 204
    assert alice.post(f"/api/devices/messages/{mid}/ack", headers=bearer(a["token"])).status_code == 204  # idempotent
    assert alice.get("/api/devices").json()["devices"][0]["pending"] == 0


def test_device_endpoints_need_valid_token(alice):
    assert alice.get("/api/devices/stream").status_code == 401
    assert alice.get("/api/devices/stream", headers=bearer("tdv_falsch")).status_code == 401
    assert alice.post("/api/devices/messages/1/ack", headers=bearer("x")).status_code == 401
    # das Sitzungs-Cookie allein genügt für Geräte-Endpunkte nicht
    assert alice.post("/api/devices/messages/1/ack").status_code == 401


def test_revoked_device_token_stops_working(alice):
    d = reg(alice)
    assert alice.delete(f"/api/devices/{d['id']}").status_code == 204
    assert alice.post("/api/devices/messages/1/ack", headers=bearer(d["token"])).status_code == 401


def test_unregister_self_and_rename(alice):
    d = reg(alice)
    assert alice.patch(f"/api/devices/{d['id']}", json={"name": "Küche"}).json()["name"] == "Küche"
    assert alice.delete("/api/devices/self", headers=bearer(d["token"])).status_code == 204
    assert alice.get("/api/devices").json()["devices"] == []


def test_users_cannot_touch_each_others_devices(client):
    make_user(client, "alice")
    login(client, "alice")
    d = reg(client)
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    make_user(client, "bob")
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username='bob'")
    login(client, "bob")
    assert client.get("/api/devices").json()["devices"] == []
    assert client.post("/api/devices/send", json={"device_id": d["id"], "title": "x"}).status_code == 404
    assert client.patch(f"/api/devices/{d['id']}", json={"name": "hack"}).status_code == 404
    assert client.delete(f"/api/devices/{d['id']}").status_code == 404


def test_notifications_are_also_delivered_to_devices(alice):
    d = reg(alice)
    with db.session() as c:
        uid = c.execute("SELECT id FROM users").fetchone()["id"]
    push._send_sync([uid], {"title": "Aufgabe fällig", "body": "Milch kaufen", "url": "/"})  # wie Erinnerungen/Bus
    with db.session() as c:
        row = c.execute("SELECT * FROM device_messages WHERE device_id = ?", (d["id"],)).fetchone()
        assert row["title"] == "Aufgabe fällig" and row["body"] == "Milch kaufen" and row["delivered_at"] is None


def test_agent_bus_device_notify(alice):
    phone, tablet = reg(alice, "Phone"), reg(alice, "Tablet")
    key = alice.post("/api/agent-bus/agents", json={"name": "ci", "scopes": ["notify"]}).json()["api_key"]
    nokey = alice.post("/api/agent-bus/agents", json={"name": "plain", "scopes": ["send"]}).json()["api_key"]

    def notify(k, payload):
        return alice.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": k},
                          json={"to": "todo", "kind": "task", "task_type": "device.notify", "payload": payload}).json()

    r = notify(key, {"device": "phone", "title": "Build fertig", "body": "main ist grün", "url": "/#/bus"})
    assert r["status"] == "completed" and r["result"] == {"queued": 1}
    assert notify(key, {"title": "An alle"})["result"] == {"queued": 2}
    assert notify(key, {"device": "gibtsnicht", "title": "x"})["status"] == "failed"
    assert notify(key, {"title": ""})["status"] == "failed"
    assert notify(key, {"title": "x", "url": "https://evil.example"})["status"] == "failed"
    assert notify(nokey, {"title": "x"})["status"] == "failed"  # Scope 'notify' fehlt
    with db.session() as c:  # (fehlgeschlagene Tasks erzeugen zusätzlich Hinweis-Benachrichtigungen - daher nach Titel zählen)
        def count(device, title):
            return c.execute("SELECT COUNT(*) FROM device_messages m JOIN devices d ON d.id = m.device_id "
                             "WHERE d.name = ? AND m.title = ?", (device, title)).fetchone()[0]
        assert count("Phone", "Build fertig") == 1 and count("Tablet", "Build fertig") == 0
        assert count("Phone", "An alle") == 1 and count("Tablet", "An alle") == 1


def test_cleanup_removes_old_delivered_messages(alice):
    d = reg(alice)
    alice.post("/api/devices/send", json={"device_id": d["id"], "title": "alt"})
    alice.post("/api/devices/send", json={"device_id": d["id"], "title": "neu"})
    from app import devices
    with db.session() as c:
        c.execute("UPDATE device_messages SET delivered_at='2000-01-01T00:00:00Z' WHERE title='alt'")
        devices.cleanup(c)
        assert [r["title"] for r in c.execute("SELECT title FROM device_messages")] == ["neu"]
