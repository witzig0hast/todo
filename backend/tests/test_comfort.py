"""Paket 7: Schnelleingabe, Papierkorb, Mehrfachauswahl, Vorlagen, Zeiterfassung, Statistik."""
from datetime import datetime, timedelta, timezone

import pytest

from app import db, stats, trash
from app.quickparse import parse
from app.recurrence import zone
from tests.conftest import login, make_user
from tests.test_planning import approve, switch

BERLIN = zone("Europe/Berlin")
NOW = datetime(2026, 10, 22, 14, 5, tzinfo=BERLIN)  # Donnerstag


def local(r):
    return datetime.strptime(r["due_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(BERLIN).strftime("%d.%m.%Y %H:%M")


# ------------------------------------------------------------------ Schnelleingabe
@pytest.mark.parametrize("text,title,due,prio", [
    ("morgen 15 Uhr Zahnarzt anrufen #privat !!", "Zahnarzt anrufen", "23.10.2026 15:00", 2),
    ("Steuer abgeben bis 31.12.", "Steuer abgeben", "31.12.2026 09:00", 0),
    ("Meeting am Montag um 10:30", "Meeting", "26.10.2026 10:30", 0),
    ("in 30 min Pizza raus", "Pizza raus", "22.10.2026 14:35", 0),
    ("Report freitag nachmittag", "Report", "23.10.2026 15:00", 0),
    ("um 7 abends joggen", "joggen", "22.10.2026 19:00", 0),
    ("Geburtstag Mama 3. März", "Geburtstag Mama", "03.03.2027 09:00", 0),
    ("heute einkaufen", "einkaufen", "22.10.2026 15:00", 0),  # 9 Uhr ist vorbei -> nächste volle Stunde
    ("Um 15.30 Uhr Call !hoch", "Call", "22.10.2026 15:30", 3),
    ("Termin 24.12.2026 18:00", "Termin", "24.12.2026 18:00", 0),
])
def test_quickparse_dates(text, title, due, prio):
    r = parse(text, NOW)
    assert (r["title"], local(r), r["priority"]) == (title, due, prio)


def test_quickparse_leaves_ambiguous_text_alone():
    for text in ("Abendessen planen", "Rechnung 2.50 Euro bezahlen", "Hallo! Wie geht's", "Montagsmaler spielen"):
        r = parse(text, NOW)
        assert r["title"] == text and r["due_at"] is None and r["priority"] == 0, text


def test_quickparse_recurrence_lists_tags():
    r = parse("Müll rausstellen @haus", NOW, {1: "Haus & Hof", 2: "Hausaufgaben"})
    assert r["title"] == "Müll rausstellen @haus" and r["list_id"] is None  # mehrdeutig -> bleibt Text
    assert parse("Müll @haus", NOW, {1: "Haus & Hof", 2: "Arbeit"})["list_id"] == 1  # eindeutiger Anfang
    r = parse("jeden Montag Müll rausstellen @arbeit #putzen", NOW, {1: "Haus", 2: "Arbeit"})
    assert (r["title"], r["list_id"], r["tags"], r["recurrence"]["freq"], local(r)) == \
        ("Müll rausstellen", 2, ["putzen"], "weekly", "26.10.2026 09:00")
    r = parse("Miete zahlen jeden 1.", NOW)
    assert (r["recurrence"]["freq"], local(r)) == ("monthly", "01.11.2026 09:00")
    r = parse("Backup werktags um 22:00 ab Erledigung", NOW)
    assert r["recurrence_text"] == "Werktags (ab Erledigung)" and local(r) == "22.10.2026 22:00"
    assert parse("alle 2 Wochen Pflanzen gießen", NOW)["recurrence_text"] == "Alle 2 Wochen"


def test_quick_endpoints(client):
    make_user(client, "anna")
    login(client, "anna")
    lst = client.post("/api/lists", json={"name": "Einkauf"}).json()
    p = client.post("/api/quick/parse", json={"text": "Milch @einkauf morgen #bio"}).json()
    assert p["title"] == "Milch" and p["list_id"] == lst["id"] and p["tags"] == ["bio"] and p["due_at"]
    t = client.post("/api/todos/quick", json={"text": "Milch @einkauf morgen #bio", "tags": ["laden"]}).json()
    assert t["title"] == "Milch" and t["list_id"] == lst["id"] and t["tags"] == ["bio", "laden"] and t["due_at"]
    raw = client.post("/api/todos/quick", json={"text": "morgen #bio", "raw": True}).json()
    assert raw["title"] == "morgen #bio" and raw["due_at"] is None
    r = client.post("/api/todos/quick", json={"text": "täglich lesen"}).json()
    assert r["recurrence"]["freq"] == "daily"


# ------------------------------------------------------------------ Papierkorb
def test_trash_restore_with_subtasks(client):
    make_user(client, "anna")
    login(client, "anna")
    t = client.post("/api/todos", json={"title": "Umzug", "due_at": "2099-01-01T10:00:00Z"}).json()
    s = client.post("/api/todos", json={"title": "Kartons", "parent_id": t["id"]}).json()
    client.post(f"/api/todos/{t['id']}/time", json={"minutes": 25})
    tid = client.delete(f"/api/todos/{t['id']}").json()["trash_id"]
    assert client.get("/api/todos").json()["todos"] == []
    entries = client.get("/api/trash").json()["entries"]
    assert entries[0]["title"] == "Umzug" and entries[0]["subtasks"] == 1
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reminders WHERE todo_id = ?", (t["id"],)).fetchone()[0] == 0
    assert client.post(f"/api/trash/{tid}/restore").json() == {"restored": 1}
    todos = {x["id"]: x for x in client.get("/api/todos").json()["todos"]}
    assert set(todos) == {t["id"], s["id"]} and todos[t["id"]]["tracked_min"] == 25
    with db.session() as conn:  # Erinnerung wieder aufgebaut
        assert conn.execute("SELECT COUNT(*) FROM reminders WHERE todo_id = ?", (t["id"],)).fetchone()[0] == 1
    assert client.get("/api/trash").json()["entries"] == []
    assert client.post(f"/api/trash/{tid}/restore").status_code == 404


def test_trash_is_private_and_purges(client):
    make_user(client, "anna")
    client.cookies.clear()
    make_user(client, "ben")
    approve("ben")
    login(client, "anna")
    t = client.post("/api/todos", json={"title": "Alt"}).json()
    tid = client.delete(f"/api/todos/{t['id']}").json()["trash_id"]
    switch(client, "ben")
    assert client.get("/api/trash").json()["entries"] == []
    assert client.post(f"/api/trash/{tid}/restore").status_code == 404
    with db.session() as conn:
        conn.execute("UPDATE trash SET deleted_at = '2000-01-01T00:00:00Z'")
    trash.purge()
    switch(client, "anna")
    assert client.get("/api/trash").json()["entries"] == []


def test_restore_into_shared_list_after_removal(client):
    make_user(client, "anna")
    client.cookies.clear()
    make_user(client, "ben")
    approve("ben")
    login(client, "anna")
    lst = client.post("/api/lists", json={"name": "WG"}).json()
    client.post(f"/api/lists/{lst['id']}/members", json={"username": "ben"})
    t = client.post("/api/todos", json={"title": "Putzplan", "list_id": lst["id"]}).json()
    switch(client, "ben")
    tid = client.delete(f"/api/todos/{t['id']}").json()["trash_id"]
    switch(client, "anna")
    client.delete(f"/api/lists/{lst['id']}/members/ben")
    switch(client, "ben")  # Ben ist raus: Wiederherstellen landet bei ihm selbst, nicht unsichtbar bei Anna
    client.post(f"/api/trash/{tid}/restore")
    mine = client.get("/api/todos").json()["todos"]
    assert [x["title"] for x in mine] == ["Putzplan"] and mine[0]["list_id"] is None


def test_clear_done_goes_to_trash(client):
    make_user(client, "anna")
    login(client, "anna")
    for n in ("A", "B"):
        x = client.post("/api/todos", json={"title": n}).json()
        client.patch(f"/api/todos/{x['id']}", json={"done": True})
    r = client.post("/api/todos/clear-done").json()
    assert r["count"] == 2
    assert client.get("/api/todos").json()["todos"] == []
    client.post(f"/api/trash/{r['trash_id']}/restore")
    assert len(client.get("/api/todos").json()["todos"]) == 2


# ------------------------------------------------------------------ Mehrfachauswahl
def test_bulk_actions(client):
    make_user(client, "anna")
    client.cookies.clear()
    make_user(client, "ben")
    approve("ben")
    login(client, "ben")
    foreign = client.post("/api/todos", json={"title": "Bens"}).json()
    switch(client, "anna")
    lst = client.post("/api/lists", json={"name": "Arbeit"}).json()
    ids = [client.post("/api/todos", json={"title": f"T{i}", "tags": ["alt"]}).json()["id"] for i in range(3)]
    assert client.post("/api/todos/bulk", json={"ids": ids + [foreign["id"]], "action": "move", "list_id": lst["id"]}).json() == {"count": 3}
    assert client.post("/api/todos/bulk", json={"ids": ids, "action": "tag", "tags": ["neu", "#Wichtig"]}).json()["count"] == 3
    client.post("/api/todos/bulk", json={"ids": ids[:1], "action": "untag", "tags": ["alt"]})
    client.post("/api/todos/bulk", json={"ids": ids, "action": "priority", "priority": 3})
    client.post("/api/todos/bulk", json={"ids": ids[:2], "action": "due", "due_at": "2099-05-01T08:00:00Z"})
    client.post("/api/todos/bulk", json={"ids": ids[2:], "action": "done"})
    todos = {x["id"]: x for x in client.get("/api/todos").json()["todos"]}
    assert todos[ids[0]]["tags"] == ["neu", "wichtig"] and todos[ids[1]]["tags"] == ["alt", "neu", "wichtig"]
    assert all(todos[i]["list_id"] == lst["id"] and todos[i]["priority"] == 3 for i in ids)
    assert todos[ids[0]]["due_at"] == "2099-05-01T08:00:00Z" and todos[ids[2]]["done"]
    assert client.post("/api/todos/bulk", json={"ids": [foreign["id"]], "action": "done"}).status_code == 404
    r = client.post("/api/todos/bulk", json={"ids": ids, "action": "delete"}).json()
    assert r["count"] == 3 and client.get("/api/todos").json()["todos"] == []
    assert client.get("/api/trash").json()["entries"][0]["title"] == "3 Aufgaben"
    client.post(f"/api/trash/{r['trash_id']}/restore")
    assert len(client.get("/api/todos").json()["todos"]) == 3
    switch(client, "ben")
    assert client.get("/api/todos").json()["todos"][0]["done"] is False  # fremde Aufgabe unberührt


# ------------------------------------------------------------------ Vorlagen
def test_templates(client):
    make_user(client, "anna")
    login(client, "anna")
    lst = client.post("/api/lists", json={"name": "Reisen"}).json()
    tpl = client.post("/api/templates", json={"name": "Urlaub", "title": "Urlaub packen", "priority": 2, "tags": ["reise"],
                                               "list_id": lst["id"], "due_days": 2, "due_time": "18:00",
                                               "subtasks": ["Pass", "Ladekabel"]}).json()
    assert tpl["subtasks"] == ["Pass", "Ladekabel"]
    t = client.post(f"/api/templates/{tpl['id']}/use", json={}).json()
    assert t["title"] == "Urlaub packen" and t["list_id"] == lst["id"] and t["priority"] == 2 and t["tags"] == ["reise"]
    due = datetime.strptime(t["due_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(BERLIN)
    assert due.strftime("%H:%M") == "18:00" and (due.date() - datetime.now(BERLIN).date()).days == 2
    subs = [x["title"] for x in client.get("/api/todos").json()["todos"] if x["parent_id"] == t["id"]]
    assert subs == ["Pass", "Ladekabel"]
    client.put(f"/api/templates/{tpl['id']}", json={"name": "Urlaub", "title": "Koffer", "due_days": None})
    t2 = client.post(f"/api/templates/{tpl['id']}/use", json={"title": "Koffer Paris"}).json()
    assert t2["title"] == "Koffer Paris" and t2["due_at"] is None
    assert client.get("/api/templates").json()["templates"][0]["used_count"] == 2
    assert client.post("/api/templates", json={"name": "x", "title": "y", "list_id": 9999}).status_code == 404
    client.delete(f"/api/templates/{tpl['id']}")
    assert client.get("/api/templates").json()["templates"] == []


# ------------------------------------------------------------------ Zeiterfassung & Statistik
def test_time_and_stats(client):
    make_user(client, "anna")
    login(client, "anna")
    client.put("/api/settings", json={"tz": "Europe/Berlin"})
    t = client.post("/api/todos", json={"title": "Fokus", "tags": ["arbeit"]}).json()
    assert client.post(f"/api/todos/{t['id']}/time", json={"minutes": 25}).json()["tracked_min"] == 25
    assert client.post(f"/api/todos/{t['id']}/time", json={"minutes": 0}).status_code == 422
    client.patch(f"/api/todos/{t['id']}", json={"done": True})
    client.post("/api/todos", json={"title": "Überfällig", "due_at": "2001-01-01T08:00:00Z"})
    with db.session() as conn:  # gestern + vorgestern auch je eine erledigt -> Serie 3
        for days in (1, 2):
            ts = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute("INSERT INTO todos (user_id, title, done, done_at, created_at, updated_at) "
                         "SELECT id, 'alt', 1, ?, ?, ? FROM users WHERE username = 'anna'", (ts, ts, ts))
    s = client.get("/api/stats").json()
    assert s["streak"] == 3 and s["overdue"] == 1 and s["open"] == 1
    assert s["week_focus_min"] == 25 and s["top_tags"] == [{"name": "arbeit", "count": 1}]
    assert sum(w["done"] for w in s["weeks"]) == 3 and sum(s["weekday"]) == 3
    assert s["longest_overdue"][0]["title"] == "Überfällig"
    assert s["review_preview"]["title"].startswith("Wochenrückblick")
    assert client.put("/api/stats/review", json={"enabled": True}).json() == {"enabled": True}
    assert client.get("/api/stats").json()["review_enabled"] is True


def test_weekly_review_sends_on_sunday_evening(client, monkeypatch):
    from app import push

    make_user(client, "anna")
    login(client, "anna")
    client.put("/api/stats/review", json={"enabled": True})
    sent = []
    monkeypatch.setattr(push, "_send_sync", lambda users, payload: sent.append(payload))

    class Sunday(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 25, 17, 30, tzinfo=timezone.utc)  # So 18:30 Berlin

    monkeypatch.setattr(stats, "datetime", Sunday)
    stats.send_weekly_reviews()
    stats.send_weekly_reviews()  # nur einmal pro Sonntag
    assert len(sent) == 1 and sent[0]["title"].startswith("Wochenrückblick")
