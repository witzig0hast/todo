"""Paket 10: API-Tokens, REST v1 (Home Assistant), MCP-Server, Benachrichtigungskanäle, Import."""
import json

import pytest

from app import channels, config, db
from tests.conftest import login, make_user
from tests.test_planning import approve, switch


@pytest.fixture()
def anna(client):
    make_user(client, "anna")
    login(client, "anna")
    client.put("/api/settings", json={"tz": "Europe/Berlin"})
    return client


def token(c, scopes=("read", "write")):
    return c.post("/api/tokens", json={"name": "HA", "scopes": list(scopes)}).json()["token"]


def test_tokens_and_rest_v1(anna):
    tok = token(anna)
    assert tok.startswith("tdk_") and anna.get("/api/tokens").json()["tokens"][0]["prefix"] == tok[:10]
    anna.post("/api/todos", json={"title": "Alt", "due_at": "2001-01-01T08:00:00Z"})
    anon = anna.__class__(anna.app)
    h = {"Authorization": f"Bearer {tok}"}
    assert anon.get("/api/v1/summary").status_code == 401
    assert anon.get("/api/v1/summary", headers={"Authorization": "Bearer tdk_falsch"}).status_code == 401
    s = anon.get("/api/v1/summary", headers=h).json()
    assert s["open"] == 1 and s["overdue"] == 1 and s["today_titles"] == ["Alt"]
    t = anon.post("/api/v1/quick", headers=h, json={"text": "morgen 9 Uhr Müll rausbringen #haushalt"}).json()  # ohne CSRF: Token-Auth
    assert t["title"] == "Müll rausbringen" and t["tags"] == ["haushalt"] and t["due_at"]
    assert anon.post(f"/api/v1/todos/{t['id']}/done", headers=h).json()["done"] is True
    assert [x["title"] for x in anon.get("/api/v1/todos", params={"due": "overdue"}, headers=h).json()["todos"]] == ["Alt"]
    ro = token(anna, ["read"])
    assert anon.post("/api/v1/quick", headers={"Authorization": f"Bearer {ro}"}, json={"text": "x"}).status_code == 403
    tid = anna.get("/api/tokens").json()["tokens"][0]["id"]
    anna.delete(f"/api/tokens/{tid}")
    assert anon.get("/api/v1/summary", headers={"Authorization": f"Bearer {ro}"}).status_code == 401
    assert anon.get("/api/todos", headers=h).status_code == 401  # Token gilt nicht für die normale App-API


def rpc(c, h, method, params=None, id_=1):
    return c.post("/api/mcp", headers=h, json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})


def test_mcp_server(anna):
    tok = token(anna)
    anon = anna.__class__(anna.app)
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/json, text/event-stream"}
    init = rpc(anon, h, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}).json()
    assert init["result"]["protocolVersion"] == "2025-06-18" and "tools" in init["result"]["capabilities"]
    assert anon.post("/api/mcp", headers=h, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    names = [t["name"] for t in rpc(anon, h, "tools/list").json()["result"]["tools"]]
    assert {"list_todos", "create_todo", "complete_todo", "update_todo", "list_lists"} <= set(names)
    r = rpc(anon, h, "tools/call", {"name": "create_todo", "arguments": {"text": "Freitag Bericht schreiben !!", "notes": "für Chef"}}).json()
    created = json.loads(r["result"]["content"][0]["text"])["created"]
    assert created["title"] == "Bericht schreiben" and created["priority"] == 2 and created["notes"] == "für Chef"
    listed = json.loads(rpc(anon, h, "tools/call", {"name": "list_todos", "arguments": {"query": "Bericht"}}).json()["result"]["content"][0]["text"])
    assert [t["id"] for t in listed["todos"]] == [created["id"]]
    upd = rpc(anon, h, "tools/call", {"name": "update_todo", "arguments": {"id": created["id"], "priority": 3, "tags": ["arbeit"]}}).json()
    assert json.loads(upd["result"]["content"][0]["text"])["updated"]["tags"] == ["arbeit"]
    bad = rpc(anon, h, "tools/call", {"name": "complete_todo", "arguments": {"id": 99999}}).json()
    assert bad["result"]["isError"] is True
    assert rpc(anon, h, "nope").json()["error"]["code"] == -32601
    ro = {"Authorization": f"Bearer {token(anna, ['read'])}"}
    assert rpc(anon, ro, "tools/call", {"name": "complete_todo", "arguments": {"id": created["id"]}}).json()["result"]["isError"] is True
    assert anon.post("/api/mcp", headers={**h, "Origin": "http://evil.example"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 403
    assert anon.get("/api/mcp", headers=h).status_code == 405
    hist = anna.get(f"/api/todos/{created['id']}/history").json()["history"]
    assert hist[0]["actor"] == "anna (HA)"  # Änderungen über Tokens sind im Verlauf erkennbar


def test_channels_send_and_ssrf(anna, monkeypatch):
    sent = []

    class FakeResp:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, **k): sent.append(("POST", url, k)); return FakeResp()
        def put(self, url, **k): sent.append(("PUT", url, k)); return FakeResp()

    monkeypatch.setattr(channels.httpx, "Client", FakeClient)
    monkeypatch.setattr(channels.socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("10.0.0.5" if host == "gotify.lan" else "93.184.216.34", port))])
    c = anna.post("/api/channels", json={"kind": "ntfy", "topic": "karims-todo", "urgent_only": True}).json()
    assert c["target"] == "https://ntfy.sh/karims-todo"
    assert anna.post("/api/channels", json={"kind": "ntfy", "topic": "bad topic!"}).status_code == 422
    assert anna.post("/api/channels", json={"kind": "telegram", "token": "123:abc", "chat_id": "42"}).status_code == 201
    # Admin (erste Person) darf ins Heimnetz, normale Nutzer nicht
    assert anna.post("/api/channels", json={"kind": "gotify", "url": "http://gotify.lan", "token": "A1"}).status_code == 201
    assert anna.post(f"/api/channels/{c['id']}/test").json() == {"ok": True}
    assert sent[-1][1] == "https://ntfy.sh" and sent[-1][2]["json"]["topic"] == "karims-todo"
    sent.clear()
    with db.session() as conn:
        uid = conn.execute("SELECT id FROM users WHERE username = 'anna'").fetchone()["id"]
        channels.deliver(conn, [uid], {"title": "Fällig", "body": "Zahnarzt", "url": "/#/today"})  # nicht dringend
    assert sorted(u for _, u, _ in sent) == ["http://gotify.lan/message", "https://api.telegram.org/bot123:abc/sendMessage"]
    sent.clear()
    with db.session() as conn:
        channels.deliver(conn, [uid], {"title": "Server down", "urgent": True})
    assert len(sent) == 3 and [k["json"]["priority"] for _, u, k in sent if "ntfy" in u] == [4]
    assert anna.post("/api/channels", json={"kind": "email", "to": "a@b.de"}).status_code == 422  # kein SMTP
    client2 = anna
    client2.post("/api/auth/logout")
    client2.cookies.clear()
    make_user(client2, "ben")
    approve("ben")
    switch(client2, "ben")
    r = client2.post("/api/channels", json={"kind": "gotify", "url": "http://gotify.lan", "token": "A1"})
    assert r.status_code == 422 and "internen Netz" in r.json()["detail"]
    assert client2.post("/api/channels", json={"kind": "gotify", "url": "https://push.example.com", "token": "A1"}).status_code == 201
    assert client2.get("/api/channels").json()["channels"][0]["target"] == "https://push.example.com"


def test_import_formats(anna):
    todoist = ("TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT,AUTHOR,RESPONSIBLE,DATE,DATE_LANG,TIMEZONE\n"
               "section,Küche,,,,,,,,\n"
               "task,Spülmaschine ausräumen @haushalt,,1,1,,,2026-11-03,en,Europe/Berlin\n"
               "task,Tabs kaufen,,4,2,,,,,\n"
               "task,Fenster putzen,,4,1,,,every saturday,en,\n")
    r = anna.post("/api/import", params={"list_name": "Zuhause"}, content=todoist.encode()).json()
    assert r["format"] == "todoist" and r["created"] == 2 and r["subtasks"] == 1 and r["lists_created"] == ["Zuhause"]
    todos = {t["title"]: t for t in anna.get("/api/todos").json()["todos"]}
    sp = todos["Spülmaschine ausräumen"]
    assert sp["priority"] == 3 and sp["tags"] == ["haushalt", "küche"] and sp["due_at"] == "2026-11-03T08:00:00Z"
    assert todos["Tabs kaufen"]["parent_id"] == sp["id"] and "every saturday" in todos["Fenster putzen"]["notes"]
    google = {"kind": "tasks#taskLists", "items": [{"title": "Arbeit", "items": [
        {"id": "a", "title": "Bericht", "notes": "Q3", "status": "needsAction", "due": "2026-11-10T00:00:00.000Z"},
        {"id": "b", "title": "Zahlen prüfen", "parent": "a", "status": "completed"},
        {"id": "c", "title": "Alt", "status": "completed"}, {"id": "d", "title": "Weg", "deleted": True}]}]}
    r = anna.post("/api/import", content=json.dumps(google).encode()).json()
    assert r["format"] == "google" and r["created"] == 2 and r["subtasks"] == 1
    todos = {t["title"]: t for t in anna.get("/api/todos").json()["todos"]}
    assert todos["Bericht"]["due_at"] == "2026-11-10T08:00:00Z" and todos["Alt"]["done"] and todos["Zahlen prüfen"]["done"]
    outlook = "Subject;Due Date;Priority;Categories;Complete\nSteuer;15.11.2026;High;Finanzen;\nAltes;1.1.2020;Normal;;Ja\n"
    r = anna.post("/api/import", content=outlook.encode("cp1252")).json()
    assert r["format"] == "csv" and r["created"] == 2
    todos = {t["title"]: t for t in anna.get("/api/todos").json()["todos"]}
    assert todos["Steuer"]["priority"] == 3 and todos["Steuer"]["tags"] == ["finanzen"] and todos["Altes"]["done"]
    assert anna.post("/api/import", content=b"Spalte;Andere\n1;2\n").status_code == 422
    # eigener Export -> Import (Wiederherstellung auf einem anderen Server)
    export = anna.get("/api/export", params={"format": "json"}).content
    before = len(anna.get("/api/todos").json()["todos"])
    r = anna.post("/api/import", content=export).json()
    assert r["format"] == "todo" and len(anna.get("/api/todos").json()["todos"]) == 2 * before
    # Rückgängig per Sammel-Löschen
    assert anna.post("/api/todos/bulk", json={"ids": r["ids"], "action": "delete"}).json()["count"] == len(r["ids"])
    assert len(anna.get("/api/todos").json()["todos"]) == before


def test_mail_channel_uses_smtp(anna, monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    mails = []
    monkeypatch.setattr(channels, "send_mail", lambda to, subject, text: mails.append((to, subject)))
    c = anna.post("/api/channels", json={"kind": "email", "to": "anna@example.com"}).json()
    anna.post(f"/api/channels/{c['id']}/test")
    assert mails == [("anna@example.com", "Todo: Test")]
