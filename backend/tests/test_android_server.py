from datetime import datetime, timezone

import pytest

from app import db, devices, events
from tests.conftest import login, make_user


@pytest.fixture()
def alice(client):
    make_user(client, "alice")
    login(client, "alice")
    client.put("/api/settings", json={"tz": "Europe/Berlin"})
    return client


def reg(c, name="Pixel"):
    return c.post("/api/devices/register", json={"name": name}).json()


def device_row(device_id):
    with db.session() as c:
        return c, c.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()


def test_quiet_until_handles_midnight_and_tz(alice):
    d = reg(alice)
    alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": "22:00", "quiet_end": "07:00"})
    with db.session() as c:
        row = c.execute("SELECT * FROM devices WHERE id = ?", (d["id"],)).fetchone()
        # 23:30 Berlin (UTC+2 im Juli) -> bis 07:00 Berlin = 05:00 UTC am Folgetag
        assert devices.quiet_until(c, row, datetime(2026, 7, 1, 21, 30, tzinfo=timezone.utc)) == "2026-07-02T05:00:00Z"
        # 03:00 Berlin -> bis 07:00 am selben Tag
        assert devices.quiet_until(c, row, datetime(2026, 7, 2, 1, 0, tzinfo=timezone.utc)) == "2026-07-02T05:00:00Z"
        # 12:00 Berlin -> keine Ruhezeit
        assert devices.quiet_until(c, row, datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)) is None


def test_messages_are_held_in_quiet_hours_and_released(alice, monkeypatch):
    d = reg(alice)
    alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": "00:00", "quiet_end": "23:59"})  # fast immer ruhig
    published = []
    monkeypatch.setattr(events, "publish", lambda ch, key, ev, data, event_id=None: published.append((ch, ev, data.get("title"))))
    r = alice.post("/api/devices/send", json={"device_id": d["id"], "title": "Leise"}).json()
    assert r["held"] == 1 and not any(p[2] == "Leise" for p in published)
    r = alice.post("/api/devices/send", json={"device_id": d["id"], "title": "Wichtig", "urgent": True}).json()
    assert r["held"] == 0 and ("device", "message", "Wichtig") in published
    # zurückgehaltene Nachricht taucht beim Verbinden noch nicht auf ...
    assert [m["title"] for m in devices._pending(d["id"])] == ["Wichtig"]
    # ... aber nach Ablauf der Ruhezeit
    with db.session() as c:
        c.execute("UPDATE device_messages SET deliver_after = '2000-01-01T00:00:00Z' WHERE title = 'Leise'")
        assert devices.release_held(c) == 1
    assert ("device", "message", "Leise") in published
    assert [m["title"] for m in devices._pending(d["id"])] == ["Leise", "Wichtig"]


def test_quiet_hours_validation_and_reset(alice):
    d = reg(alice)
    assert alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": "25:00", "quiet_end": "07:00"}).status_code == 422
    r = alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": "22:00", "quiet_end": "07:00"}).json()
    assert (r["quiet_start"], r["quiet_end"]) == ("22:00", "07:00")
    assert alice.patch(f"/api/devices/{d['id']}", json={"name": "Neu"}).json()["quiet_start"] == "22:00"  # bleibt
    r = alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": None, "quiet_end": None}).json()
    assert r["quiet_start"] is None


def test_high_priority_reminder_is_urgent(alice):
    from app import push
    d = reg(alice)
    alice.patch(f"/api/devices/{d['id']}", json={"quiet_start": "00:00", "quiet_end": "23:59"})
    alice.post("/api/todos", json={"title": "Normal", "due_at": "2020-01-01T00:00:00Z"})
    alice.post("/api/todos", json={"title": "Dringend", "due_at": "2020-01-01T00:00:00Z", "priority": 3})
    push._check_due()
    with db.session() as c:
        rows = {r["body"]: (r["urgent"], r["deliver_after"]) for r in c.execute("SELECT body, urgent, deliver_after FROM device_messages")}
    assert rows["Dringend"] == (1, None) and rows["Normal"][0] == 0 and rows["Normal"][1] is not None


def test_location_todos_and_geofences(alice, monkeypatch):
    d = reg(alice)
    calls = []
    monkeypatch.setattr(devices, "notify_geofences_changed", lambda conn, uid: calls.append(uid))
    t = alice.post("/api/todos", json={"title": "Milch kaufen", "location": {"name": "Rewe", "lat": 52.52, "lon": 13.40, "radius": 150}}).json()
    assert t["location"] == {"name": "Rewe", "lat": 52.52, "lon": 13.40, "radius": 150} and calls
    alice.post("/api/todos", json={"title": "ohne Ort"})
    assert alice.post("/api/todos", json={"title": "x", "location": {"lat": 99, "lon": 0}}).status_code == 422
    assert alice.post("/api/todos", json={"title": "x", "location": {"lat": 1, "lon": 1, "radius": 10}}).status_code == 422
    g = alice.get("/api/devices/geofences", headers={"Authorization": f"Bearer {d['token']}"}).json()["geofences"]
    assert [x["title"] for x in g] == ["Milch kaufen"] and g[0]["radius"] == 150 and g[0]["token"]
    # mit dem Token aus dem Geofence lässt sich die Aufgabe erledigen
    assert alice.post("/api/actions", json={"token": g[0]["token"], "action": "done"}).status_code == 200
    assert alice.get("/api/devices/geofences", headers={"Authorization": f"Bearer {d['token']}"}).json()["geofences"] == []
    n = len(calls)
    alice.patch(f"/api/todos/{t['id']}", json={"location": None})
    assert len(calls) == n + 1
    assert alice.get("/api/devices/geofences").status_code == 401  # nur mit Geräte-Token
