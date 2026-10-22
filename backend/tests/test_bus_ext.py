

import pytest

from app import actions, db, push, rules
from tests.conftest import login, make_user


@pytest.fixture()
def alice(client, monkeypatch):
    # Benachrichtigungen synchron statt im Hintergrund-Thread (deterministische Tests)
    monkeypatch.setattr(push, "notify_payload_threadsafe", lambda ids, payload: push._send_sync(ids, payload))
    monkeypatch.setattr(push, "notify_threadsafe", lambda ids, t, b, u="/": push._send_sync(ids, {"title": t, "body": b, "url": u}))
    make_user(client, "alice")
    login(client, "alice")
    return client


def agent(c, name="ci", scopes=("send",)):
    return c.post("/api/agent-bus/agents", json={"name": name, "scopes": list(scopes)}).json()


def test_webhook_creates_message_with_summaries(alice):
    a = agent(alice, "kuma")
    url = alice.post(f"/api/agent-bus/agents/{a['id']}/webhook").json()["url"]
    path = url.split("testserver", 1)[1]
    assert path.startswith("/api/agent-bus/hook/whk_")
    anon = alice.__class__(alice.app)  # ohne Cookies/Header
    r = anon.post(path, json={"msg": "Server down", "monitor": {"name": "web"}})
    assert r.status_code == 202
    r = anon.post(path, json={"action": "opened", "repository": {"full_name": "me/repo"}}, headers={"X-GitHub-Event": "issues"})
    r = anon.post(path, content=b"plain text alert", headers={"Content-Type": "text/plain"})
    r = anon.post(path + "?title=Mit%20Titel", json={"x": 1})
    msgs = alice.get("/api/agent-bus/messages").json()["messages"]
    assert [m["content"] for m in msgs][::-1] == ["Server down", "GitHub issues opened me/repo", "plain text alert", "Mit Titel"]
    assert all(m["from_label"] == "kuma" and m["to_label"] == "todo" for m in msgs)
    assert anon.post("/api/agent-bus/hook/whk_falsch", json={}).status_code == 404
    assert any(x["webhook"] for x in alice.get("/api/agent-bus/agents").json()["agents"])
    # deaktivieren
    alice.delete(f"/api/agent-bus/agents/{a['id']}/webhook")
    assert anon.post(path, json={"msg": "x"}).status_code == 404
    assert anon.post(path.replace("whk_", "whk_x"), content=b"x" * (70 * 1024)).status_code in (404, 413)


def test_rules_create_todo_and_notify_with_templates(alice):
    a = agent(alice, "kuma")
    dev = alice.post("/api/devices/register", json={"name": "Pixel"}).json()
    r1 = alice.post("/api/rules", json={"name": "Ausfall", "match": {"agent": "kuma", "contains": "down"},
                                        "action": {"type": "create_todo", "title": "Prüfen: {content}", "priority": 3, "tags": ["#ops"]}})
    assert r1.status_code == 201
    alice.post("/api/rules", json={"name": "Handy", "match": {"contains": "down"},
                                   "action": {"type": "notify", "title": "{agent}: {payload.monitor}", "device": "pixel", "urgent": True}})
    alice.post("/api/rules", json={"name": "Nie", "match": {"agent": "anderer"}, "action": {"type": "create_todo"}})
    url = alice.post(f"/api/agent-bus/agents/{a['id']}/webhook").json()["url"].split("testserver", 1)[1]
    alice.post(url, json={"msg": "Server DOWN", "monitor": "web-01"})
    alice.post(url, json={"msg": "Server up"})
    todos = alice.get("/api/todos").json()["todos"]
    assert [(t["title"], t["priority"], t["tags"], t["created_by"]) for t in todos] == [("Prüfen: Server DOWN", 3, ["ops"], "kuma")]
    with db.session() as c:
        titles = [r["title"] for r in c.execute("SELECT title FROM device_messages WHERE device_id = ? ORDER BY id", (dev["id"],))]
        urgent = c.execute("SELECT urgent FROM device_messages WHERE title = 'kuma: web-01'").fetchone()["urgent"]
    assert "kuma: web-01" in titles and urgent == 1
    msgs = alice.get("/api/agent-bus/messages").json()["messages"]
    down = next(m for m in msgs if m["content"] == "Server DOWN")
    assert down["rules_fired"] == ["Ausfall", "Handy"]
    ruleset = {r["name"]: r for r in alice.get("/api/rules").json()["rules"]}
    assert ruleset["Ausfall"]["fire_count"] == 1 and ruleset["Nie"]["fire_count"] == 0


def test_rule_validation_toggle_and_flood_limit(alice, monkeypatch):
    assert alice.post("/api/rules", json={"name": "leer", "match": {}, "action": {"type": "create_todo"}}).status_code == 422
    assert alice.post("/api/rules", json={"name": "x", "match": {"kind": "foo"}, "action": {"type": "create_todo"}}).status_code == 422
    r = alice.post("/api/rules", json={"name": "Alles", "match": {"kind": "text"}, "action": {"type": "create_todo", "title": "{content}"}}).json()
    assert alice.patch(f"/api/rules/{r['id']}", json={"enabled": False}).json()["enabled"] is False
    key = alice.post("/api/agent-bus/agents", json={"name": "spam", "scopes": ["send"]}).json()["api_key"]
    send = lambda t: alice.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": key}, json={"to": "todo", "kind": "text", "content": t})
    send("aus")
    assert alice.get("/api/todos").json()["todos"] == []
    alice.patch(f"/api/rules/{r['id']}", json={"enabled": True})
    monkeypatch.setattr(rules, "FIRES_PER_HOUR", 3)
    for i in range(6):
        send(f"m{i}")
    assert len(alice.get("/api/todos").json()["todos"]) == 3
    assert alice.delete(f"/api/rules/{r['id']}").status_code == 204


def test_rules_are_per_user(client):
    make_user(client, "alice")
    login(client, "alice")
    r = client.post("/api/rules", json={"name": "x", "match": {"kind": "text"}, "action": {"type": "create_todo"}}).json()
    client.post("/api/auth/logout"); client.cookies.clear(); client.headers.pop("X-CSRF-Token")
    make_user(client, "bob")
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username='bob'")
    login(client, "bob")
    assert client.get("/api/rules").json()["rules"] == []
    assert client.patch(f"/api/rules/{r['id']}", json={"enabled": False}).status_code == 404
    assert client.delete(f"/api/rules/{r['id']}").status_code == 404


def test_question_reply_from_notification_and_web(alice):
    key = agent(alice, "deploy")["api_key"]
    dev = alice.post("/api/devices/register", json={"name": "Pixel"}).json()
    q = alice.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": key}, json={
        "to": "todo", "kind": "task", "task_type": "ask", "payload": {"question": "Produktion deployen?", "options": ["Ja", "Nein", "Später", "zu viel"]}}).json()
    assert q["status"] == "pending"
    with db.session() as c:
        m = c.execute("SELECT * FROM device_messages WHERE device_id = ?", (dev["id"],)).fetchone()
    assert m["title"] == "Frage von deploy" and m["body"] == "Produktion deployen?" and m["bus_message_id"] == q["id"]
    import json as _j
    assert _j.loads(m["options"]) == ["Ja", "Nein", "Später"]
    # Antwort direkt aus der Benachrichtigung (kein Login)
    anon = alice.__class__(alice.app)
    r = anon.post("/api/actions/reply", json={"token": m["reply_token"], "text": "Ja"})
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert anon.post("/api/actions/reply", json={"token": m["reply_token"], "text": "Nein"}).status_code == 409
    # Agent sieht die Antwort
    msgs = alice.get("/api/agent-bus/messages").json()["messages"]
    assert next(x for x in msgs if x["id"] == q["id"])["result"] == {"answer": "Ja", "via": "notification"}
    # Aktions-Token für Aufgaben ist kein Antwort-Token und umgekehrt
    with db.session() as c:
        uid = c.execute("SELECT id FROM users").fetchone()["id"]
    assert anon.post("/api/actions/reply", json={"token": actions.make_token(uid, q["id"]), "text": "x"}).status_code == 403
    assert anon.post("/api/actions", json={"token": m["reply_token"], "action": "done"}).status_code == 403
    # zweite Frage, Antwort über die Web-Oberfläche
    q2 = alice.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": key}, json={
        "to": "todo", "kind": "task", "task_type": "ask", "content": "Rollback?"}).json()
    assert alice.post(f"/api/agent-bus/messages/{q2['id']}/answer", json={"text": "Nein"}).json()["result"]["answer"] == "Nein"
    assert alice.post(f"/api/agent-bus/messages/{q['id'] + 999}/answer", json={"text": "x"}).status_code == 404


def test_delivery_status_in_log(alice):
    key = agent(alice, "ci")["api_key"]
    dev = alice.post("/api/devices/register", json={"name": "Pixel"}).json()
    msg = alice.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": key},
                     json={"to": "todo", "kind": "text", "content": "Build grün"}).json()
    log = {m["id"]: m for m in alice.get("/api/agent-bus/messages").json()["messages"]}
    assert log[msg["id"]]["deliveries"] == [{"device": "Pixel", "delivered_at": None}]
    with db.session() as c:
        dm = c.execute("SELECT id FROM device_messages WHERE bus_message_id = ?", (msg["id"],)).fetchone()["id"]
    alice.post(f"/api/devices/messages/{dm}/ack", headers={"Authorization": f"Bearer {dev['token']}"})
    log = {m["id"]: m for m in alice.get("/api/agent-bus/messages").json()["messages"]}
    assert log[msg["id"]]["deliveries"][0]["delivered_at"] is not None
    # Nachricht an einen Agent: "abgeholt" sobald die Inbox gelesen wurde
    out = alice.post("/api/agent-bus/messages", json={"to": "ci", "kind": "text", "content": "Hallo"}).json()
    assert out["delivered_at"] is None
    alice.get("/api/agent-bus/inbox", headers={"X-Agent-Key": key})
    log = {m["id"]: m for m in alice.get("/api/agent-bus/messages").json()["messages"]}
    assert log[out["id"]]["delivered_at"] is not None

