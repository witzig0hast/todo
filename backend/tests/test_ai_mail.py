from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from app import assistant, db, mailin, ollama, push
from tests.conftest import login, make_user


@pytest.fixture()
def alice(client):
    make_user(client, "alice")
    login(client, "alice")
    client.put("/api/settings", json={"tz": "Europe/Berlin"})
    return client


def uid():
    with db.session() as c:
        return c.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()["id"]


def test_normalize_actions_is_strict(alice):
    t = alice.post("/api/todos", json={"title": "Zahnarzt anrufen"}).json()
    alice.post("/api/agent-bus/agents", json={"name": "deploy"})
    with db.session() as c:
        acts = assistant.normalize_actions(c, uid(), [
            {"type": "create", "title": "Milch", "due_at": "2030-05-01T15:00", "priority": 9, "tags": ["#Einkauf", "ungültig tag"]},
            {"type": "complete", "todo_id": t["id"]},
            {"type": "complete", "todo_id": 99999},                    # fremd/erfunden -> verworfen
            {"type": "reschedule", "todo_id": t["id"], "due_at": "2030-05-02T09:00"},
            {"type": "snooze", "todo_id": t["id"], "minutes": 999999},
            {"type": "message_agent", "agent": "DEPLOY", "content": "Start"},
            {"type": "message_agent", "agent": "unbekannt", "content": "x"},
            {"type": "delete_everything"}, "kein dict", {"type": "create", "title": ""},
        ], tz_offset=-120)
    kinds = [a["type"] for a in acts]
    assert kinds == ["create", "complete", "reschedule", "snooze", "message_agent"]
    assert acts[0]["due_at"] == "2030-05-01T13:00:00Z" and acts[0]["priority"] == 3 and acts[0]["tags"] == []
    assert acts[3]["minutes"] == 7 * 1440 and acts[4]["agent"] == "deploy"
    with db.session() as c:
        assert assistant.normalize_actions(c, uid(), "kein array", 0) == []


def test_interpret_multiple_tasks_and_commands(alice, monkeypatch):
    t = alice.post("/api/todos", json={"title": "Zahnarzt anrufen"}).json()
    seen = {}

    async def fake(model, messages):
        seen["system"] = messages[0]["content"]
        return {"reply": "Okay", "actions": [
            {"type": "create", "title": "Milch kaufen"}, {"type": "create", "title": "Müll rausbringen", "due_at": "2030-01-02T09:00"},
            {"type": "complete", "todo_id": t["id"]}]}

    monkeypatch.setattr(ollama, "chat_json", fake)
    r = alice.post("/api/ai/interpret", json={"text": "Milch kaufen, morgen Müll raus und Zahnarzt erledigt",
                                              "now_local": "2030-01-01T10:00", "tz_offset": -60}).json()
    assert [a["label"] for a in r["actions"]] == ["Neue Aufgabe: Milch kaufen", "Neue Aufgabe: Müll rausbringen", "Erledigt: Zahnarzt anrufen"]
    assert f"#{t['id']}" in seen["system"]  # Kontext enthält die Aufgaben-IDs
    # nichts wurde ausgeführt
    assert not alice.get("/api/todos").json()["todos"][0]["done"]


def test_chat_returns_reply_and_actions(alice, monkeypatch):
    async def fake(model, messages):
        return {"reply": "Mach zuerst das Angebot.", "actions": [{"type": "create", "title": "Angebot"}]}

    monkeypatch.setattr(ollama, "chat_json", fake)
    r = alice.post("/api/ai/chat", json={"now_local": "2030-01-01T10:00", "tz_offset": 0,
                                         "messages": [{"role": "user", "content": "Was zuerst?"}]}).json()
    assert r["reply"] == "Mach zuerst das Angebot." and r["actions"][0]["title"] == "Angebot"


def test_daily_summary_once_per_day(alice, monkeypatch):
    sent = []
    monkeypatch.setattr(push, "_send_sync", lambda ids, payload: sent.append(payload))
    alice.post("/api/todos", json={"title": "Überfällig", "due_at": "2020-01-01T08:00:00Z", "priority": 3})
    alice.post("/api/todos", json={"title": "Irgendwann"})
    assert alice.put("/api/ai/summary", json={"time": "25:00"}).status_code == 422
    alice.put("/api/ai/summary", json={"time": "00:00"})
    assert alice.get("/api/settings").json()["summary_time"] == "00:00"
    assistant.send_daily_summaries()
    assistant.send_daily_summaries()
    assert len(sent) == 1 and sent[0]["title"] == "Dein Tag: 1 Aufgabe, 1 überfällig" and sent[0]["body"] == "Überfällig"
    alice.put("/api/ai/summary", json={"time": "23:59"})
    with db.session() as c:
        c.execute("UPDATE user_settings SET summary_sent_on = NULL")
    local = datetime.now(timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Europe/Berlin"))
    assistant.send_daily_summaries()
    assert len(sent) == (2 if local.strftime("%H:%M") >= "23:59" else 1)
    assert alice.post("/api/ai/summary/preview").json()["title"].startswith("Dein Tag")


def _mail(sender, subject, text=None, html=None):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = "todo@example.com"
    m["Subject"] = subject
    if text:
        m.set_content(text)
    if html:
        m.add_alternative(html, subtype="html") if text else m.set_content(html, subtype="html")
    return m.as_bytes()


def test_import_message_rules(alice):
    allowed = {"karim@example.com"}
    with db.session() as c:
        assert mailin.import_message(c, uid(), _mail("Karim <KARIM@example.com>", "AW: Angebot schicken #arbeit", "Bis Freitag"), allowed)
        assert not mailin.import_message(c, uid(), _mail("spam@evil.example", "Gewinnspiel", "x"), allowed)
        assert mailin.import_message(c, uid(), _mail("karim@example.com", "", html="<p>Hallo <b>Welt</b></p><script>alert(1)</script>"), allowed)
    todos = alice.get("/api/todos").json()["todos"]
    assert [(t["title"], t["tags"], t["created_by"]) for t in todos] == [
        ("Angebot schicken", ["arbeit", "mail"], "mail"), ("(ohne Betreff)", ["mail"], "mail")]
    assert "Bis Freitag" in todos[0]["notes"] and "alert" not in todos[1]["notes"] and "Welt" in todos[1]["notes"]


def test_mail_config_encrypts_password_and_validates(alice):
    assert alice.put("/api/mail", json={"host": "imap.example.com", "port": 25, "username": "u", "password": "p",
                                        "allowed_senders": ["a@b.de"]}).status_code == 422
    assert alice.put("/api/mail", json={"host": "imap.example.com", "username": "u", "password": "p",
                                        "allowed_senders": ["keine-adresse"]}).status_code == 422
    assert alice.put("/api/mail", json={"host": "imap.example.com", "username": "u", "allowed_senders": ["a@b.de"]}).status_code == 422
    r = alice.put("/api/mail", json={"host": "imap.example.com", "username": "u", "password": "geheim123",
                                     "allowed_senders": ["Karim@Example.com"]}).json()
    assert r["configured"] and r["allowed_senders"] == ["karim@example.com"] and "password" not in r
    with db.session() as c:
        enc = c.execute("SELECT password_enc FROM mail_accounts").fetchone()["password_enc"]
    assert "geheim123" not in enc
    # ohne Passwort aktualisieren behält das alte
    alice.put("/api/mail", json={"host": "imap2.example.com", "username": "u", "allowed_senders": ["a@b.de"]})
    with db.session() as c:
        assert c.execute("SELECT password_enc FROM mail_accounts").fetchone()["password_enc"] == enc
    assert alice.delete("/api/mail").status_code == 204
    assert alice.get("/api/mail").json() == {"configured": False}


def test_poll_with_fake_imap(alice, monkeypatch):
    alice.put("/api/mail", json={"host": "imap.example.com", "username": "u", "password": "pw",
                                 "allowed_senders": ["karim@example.com"]})
    mails = {b"1": _mail("karim@example.com", "Steuer abgeben #finanzen", "bis 31.7."), b"2": _mail("x@spam.example", "Spam", "x")}
    flagged = []

    class FakeImap:
        def search(self, *_):
            return "OK", [b" ".join(mails)]

        def fetch(self, mid, _):
            return "OK", [(b"1 (BODY[] {n}", mails[mid]), b")"]

        def store(self, mid, *_):
            flagged.append(mid)

        def logout(self):
            pass

    calls = []
    monkeypatch.setattr(mailin, "_connect", lambda *a: calls.append(a) or FakeImap())
    mailin.poll_due_accounts()
    assert calls[0][3] == "pw"  # entschlüsselt übergeben
    assert flagged == [b"1", b"2"]
    assert [t["title"] for t in alice.get("/api/todos").json()["todos"]] == ["Steuer abgeben"]
    st = alice.get("/api/mail").json()
    assert st["imported"] == 1 and st["last_error"] is None and st["last_check_at"]
    mailin.poll_due_accounts()  # zu früh -> kein erneuter Abruf
    assert len(calls) == 1


def test_poll_error_is_recorded_generic(alice, monkeypatch):
    alice.put("/api/mail", json={"host": "imap.example.com", "username": "u", "password": "pw", "allowed_senders": ["a@b.de"]})

    def boom(*a):
        raise OSError("connection refused to 10.0.0.5:993")  # Details nicht an den Client

    monkeypatch.setattr(mailin, "_connect", boom)
    mailin.poll_due_accounts()
    assert alice.get("/api/mail").json()["last_error"] == "Verbindung oder Anmeldung fehlgeschlagen"
