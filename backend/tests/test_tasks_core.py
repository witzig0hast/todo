from datetime import datetime, timezone

import pytest

from app import actions, db, push
from app.recurrence import Recurrence, next_due, zone
from tests.conftest import login, make_user

BERLIN = zone("Europe/Berlin")


def utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ Wiederholungs-Rechnung
def test_daily_keeps_wall_clock_across_dst():
    # Sa 25.10.2025 09:00 Berlin (UTC+2) -> So 26.10. 09:00 Berlin (UTC+1, Zeitumstellung)
    nxt = next_due(Recurrence(freq="daily"), "2025-10-25T07:00:00Z", "2025-10-25T08:00:00Z", BERLIN,
                   now=utc("2025-10-25T08:00:00Z"))
    assert nxt == "2025-10-26T08:00:00Z"


def test_monthly_clamps_to_month_end():
    nxt = next_due(Recurrence(freq="monthly"), "2026-01-31T08:00:00Z", "2026-01-31T09:00:00Z", BERLIN,
                   now=utc("2026-01-31T09:00:00Z"))
    assert nxt == "2026-02-28T08:00:00Z"


def test_weekdays_skips_weekend():
    # Fr 2026-10-23 09:00 -> Mo 2026-10-26 09:00 (Berlin, beide UTC+2 bzw. +1 nach Umstellung am 25.10.)
    nxt = next_due(Recurrence(freq="weekdays"), "2026-10-23T07:00:00Z", "2026-10-23T08:00:00Z", BERLIN,
                   now=utc("2026-10-23T08:00:00Z"))
    assert nxt == "2026-10-26T08:00:00Z"


def test_skips_missed_occurrences_but_after_done_counts_from_completion():
    rec = Recurrence(freq="weekly")
    # seit Wochen überfällig: nächste Instanz liegt in der Zukunft, gleiche Uhrzeit, gleicher Wochentag
    nxt = next_due(rec, "2026-09-01T07:00:00Z", "2026-10-21T10:00:00Z", BERLIN, now=utc("2026-10-21T10:00:00Z"))
    assert utc(nxt) > utc("2026-10-21T10:00:00Z") and utc(nxt).astimezone(BERLIN).weekday() == 1
    after = next_due(Recurrence(freq="daily", interval=3, after_done=True), "2026-09-01T07:00:00Z",
                     "2026-10-21T10:00:00Z", BERLIN, now=utc("2026-10-21T10:00:00Z"))
    assert after == "2026-10-24T07:00:00Z"  # 3 Tage nach Erledigung, Uhrzeit der alten Fälligkeit (09:00)


# ------------------------------------------------------------------ API
@pytest.fixture()
def alice(client):
    make_user(client, "alice")
    login(client, "alice")
    return client


def test_recurring_todo_spawns_next_with_subtasks(alice):
    t = alice.post("/api/todos", json={"title": "Müll rausbringen", "due_at": "2030-01-07T07:00:00Z",
                                        "recurrence": {"freq": "weekly"}, "tags": ["#Haushalt"],
                                        "remind_offsets": [0, 60]}).json()
    assert t["recurrence_text"] == "Wöchentlich" and t["tags"] == ["haushalt"] and t["remind_offsets"] == [0, 60]
    alice.post("/api/todos", json={"title": "Gelbe Tonne", "parent_id": t["id"]})
    r = alice.patch(f"/api/todos/{t['id']}", json={"done": True}).json()
    nxt = r["next"]
    assert nxt["due_at"] == "2030-01-14T07:00:00Z" and not nxt["done"] and nxt["tags"] == ["haushalt"]
    todos = alice.get("/api/todos").json()["todos"]
    assert [x["title"] for x in todos if x["parent_id"] == nxt["id"]] == ["Gelbe Tonne"]
    # erneutes "erledigt" auf der alten Aufgabe erzeugt keine weitere Instanz
    alice.patch(f"/api/todos/{t['id']}", json={"done": True})
    assert sum(1 for x in alice.get("/api/todos").json()["todos"] if x["title"] == "Müll rausbringen") == 2


def test_recurrence_can_be_removed_and_validated(alice):
    t = alice.post("/api/todos", json={"title": "x", "recurrence": {"freq": "daily"}}).json()
    assert alice.patch(f"/api/todos/{t['id']}", json={"recurrence": None}).json()["recurrence"] is None
    assert alice.post("/api/todos", json={"title": "x", "recurrence": {"freq": "hourly"}}).status_code == 422
    assert alice.post("/api/todos", json={"title": "x", "recurrence": {"freq": "daily", "interval": 0}}).status_code == 422


def test_reminder_rows_follow_offsets_and_done(alice):
    t = alice.post("/api/todos", json={"title": "Termin", "due_at": "2030-05-01T10:00:00Z", "remind_offsets": [0, 30, 1440]}).json()
    with db.session() as c:
        rows = [r["remind_at"] for r in c.execute("SELECT remind_at FROM reminders WHERE todo_id = ? ORDER BY remind_at", (t["id"],))]
    assert rows == ["2030-04-30T10:00:00Z", "2030-05-01T09:30:00Z", "2030-05-01T10:00:00Z"]
    alice.patch(f"/api/todos/{t['id']}", json={"due_at": "2030-06-01T10:00:00Z", "remind_offsets": [0]})
    with db.session() as c:
        assert [r["remind_at"] for r in c.execute("SELECT remind_at FROM reminders WHERE todo_id = ?", (t["id"],))] == ["2030-06-01T10:00:00Z"]
    alice.patch(f"/api/todos/{t['id']}", json={"done": True})
    with db.session() as c:
        assert c.execute("SELECT COUNT(*) FROM reminders WHERE todo_id = ? AND sent = 0", (t["id"],)).fetchone()[0] == 0
    assert alice.post("/api/todos", json={"title": "x", "remind_offsets": [-5]}).status_code == 422
    assert alice.post("/api/todos", json={"title": "x", "remind_offsets": [1, 2, 3, 4, 5, 6]}).status_code == 422


def test_due_reminder_and_snooze_are_delivered_with_action_token(alice):
    dev = alice.post("/api/devices/register", json={"name": "Pixel"}).json()
    t = alice.post("/api/todos", json={"title": "Zahnarzt anrufen", "due_at": "2020-01-01T08:00:00Z"}).json()
    push._check_due()
    with db.session() as c:
        m = c.execute("SELECT * FROM device_messages WHERE device_id = ?", (dev["id"],)).fetchone()
    assert m["title"] == "Aufgabe fällig" and m["body"] == "Zahnarzt anrufen" and m["todo_id"] == t["id"]
    uid, tid = actions.read_token(m["action_token"])
    assert tid == t["id"]
    push._check_due()  # nicht doppelt
    with db.session() as c:
        assert c.execute("SELECT COUNT(*) FROM device_messages").fetchone()[0] == 1
    # Schlummern über die Benachrichtigung: 10 Minuten später
    r = alice.post("/api/actions", json={"token": m["action_token"], "action": "snooze", "minutes": 10})
    assert r.status_code == 200 and r.json()["title"] == "Zahnarzt anrufen"
    with db.session() as c:
        snz = c.execute("SELECT * FROM reminders WHERE todo_id = ? AND offset_min IS NULL AND sent = 0", (t["id"],)).fetchone()
    assert snz is not None
    with db.session() as c:  # Zeit vorspulen
        c.execute("UPDATE reminders SET remind_at = '2020-01-01T00:00:00Z' WHERE id = ?", (snz["id"],))
    push._check_due()
    with db.session() as c:
        titles = [r["title"] for r in c.execute("SELECT title FROM device_messages ORDER BY id")]
    assert titles == ["Aufgabe fällig", "Erinnerung"]


def test_action_done_without_session(alice, client):
    t = alice.post("/api/todos", json={"title": "Rechnung zahlen"}).json()
    with db.session() as c:
        uid = c.execute("SELECT id FROM users").fetchone()["id"]
    token = actions.make_token(uid, t["id"])
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    r = client.post("/api/actions", json={"token": token, "action": "done"})
    assert r.status_code == 200
    with db.session() as c:
        assert c.execute("SELECT done FROM todos WHERE id = ?", (t["id"],)).fetchone()["done"] == 1


def test_action_token_tampering_and_expiry(alice):
    t = alice.post("/api/todos", json={"title": "x"}).json()
    with db.session() as c:
        uid = c.execute("SELECT id FROM users").fetchone()["id"]
    good = actions.make_token(uid, t["id"])
    forged = actions.make_token(uid, t["id"] + 1)[:-4] + good[-4:]
    assert alice.post("/api/actions", json={"token": forged, "action": "done"}).status_code == 403
    assert alice.post("/api/actions", json={"token": "abc.def.ghi", "action": "done"}).status_code == 403
    expired = actions.make_token(uid, t["id"], ttl=-10)
    assert alice.post("/api/actions", json={"token": expired, "action": "done"}).status_code == 403
    # Token eines anderen Benutzers greift nicht auf fremde Aufgaben
    other = actions.make_token(uid + 999, t["id"])
    assert alice.post("/api/actions", json={"token": other, "action": "done"}).status_code == 403


def test_tags_search_and_filters(alice):
    alice.post("/api/todos", json={"title": "Angebot Müller", "tags": ["arbeit", "Dringend"], "priority": 3})
    alice.post("/api/todos", json={"title": "Milch", "notes": "laktosefrei", "tags": ["einkauf"]})
    assert alice.post("/api/todos", json={"title": "x", "tags": ["mit leerzeichen"]}).status_code == 422
    assert [t["title"] for t in alice.get("/api/todos?q=laktose").json()["todos"]] == ["Milch"]
    assert [t["title"] for t in alice.get("/api/todos?tag=dringend").json()["todos"]] == ["Angebot Müller"]
    assert alice.get("/api/todos?q=100%25").json()["todos"] == []  # Wildcards werden escaped
    tags = alice.get("/api/tags").json()["tags"]
    assert {t["name"] for t in tags} == {"arbeit", "dringend", "einkauf"}
    f = alice.post("/api/filters", json={"name": "Wichtig", "query": {"tags": ["#Arbeit"], "priority_min": 2}}).json()
    assert f["query"]["tags"] == ["arbeit"] and f["query"]["due"] == "any"
    assert [x["name"] for x in alice.get("/api/filters").json()["filters"]] == ["Wichtig"]
    assert alice.post("/api/filters", json={"name": "x", "query": {"due": "gestern"}}).status_code == 422
    assert alice.delete(f"/api/filters/{f['id']}").status_code == 204


def test_timezone_setting(alice):
    assert alice.put("/api/settings", json={"tz": "America/New_York"}).json()["tz"] == "America/New_York"
    assert alice.put("/api/settings", json={"tz": "Mars/Olympus"}).status_code == 422
    assert alice.put("/api/settings", json={"ollama_model": "x"}).json()["tz"] == "America/New_York"  # bleibt erhalten


def test_existing_due_todos_are_migrated_to_reminders(client):
    make_user(client, "alice")
    login(client, "alice")
    with db.session() as c:
        uid = c.execute("SELECT id FROM users").fetchone()["id"]
        c.execute("INSERT INTO todos (user_id, title, due_at, created_at, updated_at) VALUES (?, 'alt', '2030-01-01T00:00:00Z', ?, ?)",
                  (uid, db.now(), db.now()))
        c.execute("DELETE FROM settings WHERE key = 'migrated_reminders'")
    db.init_db()
    with db.session() as c:
        assert c.execute("SELECT COUNT(*) FROM reminders r JOIN todos t ON t.id = r.todo_id WHERE t.title = 'alt'").fetchone()[0] == 1
    db.init_db()  # idempotent
    with db.session() as c:
        assert c.execute("SELECT COUNT(*) FROM reminders r JOIN todos t ON t.id = r.todo_id WHERE t.title = 'alt'").fetchone()[0] == 1
