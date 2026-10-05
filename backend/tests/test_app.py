import asyncio
import io
import json
import wave

from app import config, wyoming
from app.main import app  # noqa: F401
from tests.conftest import login, make_user


def test_first_user_admin_then_pending(client):
    r = make_user(client, "alice")
    assert r == {"status": "approved", "admin": True}
    me = client.get("/api/auth/me").json()
    assert me["user"]["role"] == "admin"
    client.cookies.clear()
    assert make_user(client, "bob")["status"] == "pending"
    r = client.post("/api/auth/login", json={"username": "bob", "password": "passwort-12345"})
    assert r.status_code == 403 and "Freigabe" in r.json()["detail"]
    login(client, "alice")
    users = client.get("/api/admin/users").json()["users"]
    bob = next(u for u in users if u["username"] == "bob")
    assert client.post(f"/api/admin/users/{bob['id']}/approve").status_code == 200
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    login(client, "bob")
    assert client.get("/api/admin/users").status_code == 403


def test_csrf_and_auth_required(client):
    make_user(client, "alice")
    login(client, "alice")
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/todos", json={"title": "x"}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/api/todos", json={"title": "x"}).status_code == 201
    client.cookies.clear()
    assert client.get("/api/todos").status_code == 401


def test_login_lockout_and_wrong_password(client):
    make_user(client, "alice")
    client.cookies.clear()
    for _ in range(config.LOGIN_MAX_FAILURES):
        assert client.post("/api/auth/login", json={"username": "alice", "password": "falsch"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": "passwort-12345"}).status_code == 429


def test_isolation_between_users(client):
    make_user(client, "alice")
    login(client, "alice")
    tid = client.post("/api/todos", json={"title": "geheim"}).json()["id"]
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    make_user(client, "bob")  # pending
    from app import db
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username='bob'")
    login(client, "bob")
    assert client.get("/api/todos").json()["todos"] == []
    assert client.patch(f"/api/todos/{tid}", json={"done": True}).status_code == 404
    assert client.delete(f"/api/todos/{tid}").status_code == 404


def test_todos_lists_subtasks(client):
    make_user(client, "alice")
    login(client, "alice")
    lid = client.post("/api/lists", json={"name": "Arbeit", "color": "#112233"}).json()["id"]
    t = client.post("/api/todos", json={"title": "A", "list_id": lid, "due_at": "2030-01-01T10:00:00+01:00",
                                         "priority": 2}).json()
    assert t["due_at"] == "2030-01-01T09:00:00Z"
    sub = client.post("/api/todos", json={"title": "sub", "parent_id": t["id"]})
    assert sub.status_code == 201
    assert client.post("/api/todos", json={"title": "x", "parent_id": sub.json()["id"]}).status_code == 422
    done = client.patch(f"/api/todos/{t['id']}", json={"done": True}).json()
    assert done["done"] and done["done_at"]
    assert client.post("/api/todos", json={"title": "x", "priority": 9}).status_code == 422


def test_agent_bus_flow(client):
    make_user(client, "alice")
    login(client, "alice")
    r = client.post("/api/agent-bus/agents", json={"name": "shop", "scopes": ["send", "todos:write"]})
    assert r.status_code == 201
    key = r.json()["api_key"]
    assert client.post("/api/agent-bus/agents", json={"name": "todo"}).status_code == 422
    assert client.post("/api/agent-bus/agents", json={"name": "shop"}).status_code == 409
    other = client.post("/api/agent-bus/agents", json={"name": "reader", "scopes": ["send"]}).json()["api_key"]
    H = {"X-Agent-Key": key}
    # Agent legt per Task ein Todo an
    r = client.post("/api/agent-bus/agent/messages", headers=H, json={
        "to": "todo", "kind": "task", "task_type": "todo.create", "payload": {"title": "Backup prüfen"}})
    assert r.status_code == 201 and r.json()["status"] == "completed"
    assert any(t["created_by"] == "shop" for t in client.get("/api/todos").json()["todos"])
    # Ohne Scope scheitert die Task
    r = client.post("/api/agent-bus/agent/messages", headers={"X-Agent-Key": other}, json={
        "to": "todo", "kind": "task", "task_type": "todo.list"})
    assert r.json()["status"] == "failed"
    # Nutzer -> Agent, Inbox, Ergebnis
    m = client.post("/api/agent-bus/messages", json={"to": "shop", "kind": "task", "task_type": "report"}).json()
    assert m["status"] == "pending"
    inbox = client.get("/api/agent-bus/inbox", headers=H).json()["messages"]
    assert [x["id"] for x in inbox] == [m["id"]]
    assert client.post(f"/api/agent-bus/messages/{m['id']}/result", headers={"X-Agent-Key": other},
                       json={"status": "completed"}).status_code == 404
    r = client.post(f"/api/agent-bus/messages/{m['id']}/result", headers=H,
                    json={"status": "completed", "result": {"ok": 1}})
    assert r.json()["status"] == "completed" and r.json()["result"] == {"ok": 1}
    assert client.get("/api/agent-bus/inbox", headers={"X-Agent-Key": "nope"}).status_code == 401
    assert len(client.get("/api/agent-bus/messages").json()["messages"]) >= 3
    # Key-Rotation macht den alten Key ungültig
    aid = client.get("/api/agent-bus/agents").json()["agents"][0]["id"]
    client.post(f"/api/agent-bus/agents/{aid}/rotate")
    assert client.get("/api/agent-bus/inbox", headers=H).status_code == 401


def _wav(seconds=0.2, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * seconds))
    return buf.getvalue()


def test_voice_via_fake_wyoming_server(client, monkeypatch):
    received = []

    async def handler(reader, writer):
        total = 0
        while True:
            header = json.loads(await reader.readline())
            if header.get("payload_length"):
                total += len(await reader.readexactly(header["payload_length"]))
            received.append(header["type"])
            if header["type"] == "audio-stop":
                break
        writer.write(json.dumps({"type": "transcript", "data": {"text": " Hallo Welt "}}).encode() + b"\n")
        await writer.drain()
        writer.close()
        received.append(total)

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setattr(config, "WHISPER_HOST", "127.0.0.1")
        monkeypatch.setattr(config, "WHISPER_PORT", port)
        async with server:
            return await wyoming.transcribe(wyoming.wav_to_pcm(_wav()))

    assert asyncio.run(run()) == "Hallo Welt"
    assert received[0] == "transcribe" and received[1] == "audio-start" and "audio-chunk" in received
    assert received[-1] == 6400


def test_voice_rejects_bad_audio(client):
    make_user(client, "alice")
    login(client, "alice")
    assert client.post("/api/voice/transcribe", content=b"nicht wav").status_code == 422
    assert client.post("/api/voice/transcribe", content=_wav(rate=44100)).status_code == 422


def test_ai_parse_with_mock(client, monkeypatch):
    from app import ollama

    async def fake(model, messages):
        return {"title": "Zahnarzt anrufen", "priority": "2", "due_at": "2030-05-01T15:00"}

    monkeypatch.setattr(ollama, "chat_json", fake)
    make_user(client, "alice")
    login(client, "alice")
    r = client.post("/api/ai/parse", json={"text": "morgen 15 Uhr Zahnarzt", "now_local": "2030-04-30T10:00",
                                           "tz_offset": -120})
    assert r.status_code == 200
    assert r.json()["due_at"] == "2030-05-01T13:00:00Z" and r.json()["priority"] == 2


def test_security_headers(client):
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
