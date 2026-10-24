"""Paket 9: Foto -> Aufgaben, Wochenplanung, semantische Suche, Duplikate, Tag-Vorschläge (Ollama gemockt)."""
import math

import pytest

from app import ai_tools, db, ollama
from tests.conftest import login, make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
CTX = {"now_local": "2030-01-01T10:00", "tz_offset": -60}


@pytest.fixture()
def anna(client):
    make_user(client, "anna")
    login(client, "anna")
    return client


def test_photo_creates_only_create_actions(anna, monkeypatch):
    t = anna.post("/api/todos", json={"title": "Alt"}).json()
    seen = {}

    async def fake(model, messages):
        seen["model"], seen["images"] = model, messages[1].get("images")
        return {"reply": "Ein Brief vom Finanzamt", "actions": [
            {"type": "create", "title": "Steuer nachzahlen", "due_at": "2030-02-15T09:00", "notes": "Aktenzeichen 123"},
            {"type": "complete", "todo_id": t["id"]}]}

    monkeypatch.setattr(ollama, "chat_json", fake)
    r = anna.post("/api/ai/photo", params=CTX, content=PNG)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [a["title"] for a in body["actions"]] == ["Steuer nachzahlen"] and body["actions"][0]["due_at"] == "2030-02-15T08:00:00Z"
    assert seen["model"] == "qwen2.5vl:7b" and len(seen["images"]) == 1
    anna.put("/api/settings", json={"vision_model": "llava:7b"})
    anna.post("/api/ai/photo", params=CTX, content=PNG)
    assert seen["model"] == "llava:7b"
    assert anna.post("/api/ai/photo", params=CTX, content=b"<html>").status_code == 415
    assert anna.get("/api/todos").json()["todos"][0]["title"] == "Alt"  # nichts ohne Bestätigung angelegt


def test_weekplan_only_reschedules_own(anna, monkeypatch):
    t = anna.post("/api/todos", json={"title": "Bericht"}).json()

    async def fake(model, messages):
        assert f"#{t['id']}" in messages[0]["content"]
        return {"reply": "Plan", "actions": [{"type": "reschedule", "todo_id": t["id"], "due_at": "2030-01-03T10:00"},
                                             {"type": "reschedule", "todo_id": 99999, "due_at": "2030-01-03T10:00"},
                                             {"type": "create", "title": "Neu"}]}

    monkeypatch.setattr(ollama, "chat_json", fake)
    r = anna.post("/api/ai/weekplan", json=CTX).json()
    assert r["actions"] == [{"type": "reschedule", "todo_id": t["id"], "due_at": "2030-01-03T09:00:00Z", "label": "Verschieben: Bericht"}]


def _fake_embed(texts):
    # Spielzeug-Embedding: Wortfelder -> Achsen
    fields = [("auto", "tüv", "werkstatt", "reifen"), ("milch", "brot", "einkaufen"), ("steuer", "finanzamt")]
    out = []
    for t in texts:
        low = t.lower()
        out.append([sum(w in low for w in f) + 0.01 for f in fields])
    return out


def test_semantic_search_indexes_and_ranks(anna, monkeypatch):
    calls = []

    async def fake_embed(model, inputs):
        calls.append(len(inputs))
        return _fake_embed(inputs)

    monkeypatch.setattr(ollama, "embed", fake_embed)
    car = anna.post("/api/todos", json={"title": "TÜV-Termin machen"}).json()
    anna.post("/api/todos", json={"title": "Milch und Brot"})
    r = anna.get("/api/ai/search", params={"q": "Auto Werkstatt"}).json()
    assert r["results"][0]["id"] == car["id"] and r["model"] == "bge-m3" and r["pending"] == 0
    assert calls == [2, 1]  # zwei Aufgaben indexiert + Suchanfrage
    anna.get("/api/ai/search", params={"q": "Reifen"})
    assert calls == [2, 1, 1]  # Index wiederverwendet
    anna.patch(f"/api/todos/{car['id']}", json={"title": "Reifen wechseln"})
    anna.get("/api/ai/search", params={"q": "Reifen"})
    assert calls[-2:] == [1, 1]  # nur die geänderte Aufgabe neu


def test_background_indexing(anna, monkeypatch):
    monkeypatch.setattr(ollama, "embed_sync", lambda model, inputs: _fake_embed(inputs))

    async def fake_embed(model, inputs):
        return _fake_embed(inputs)

    monkeypatch.setattr(ollama, "embed", fake_embed)
    anna.get("/api/ai/search", params={"q": "x y"})  # aktiviert Hintergrund-Indexierung
    anna.post("/api/todos", json={"title": "Finanzamt anrufen"})
    ai_tools.index_embeddings()
    with db.session() as c:
        assert c.execute("SELECT COUNT(*) FROM todo_embeddings").fetchone()[0] == 1


def test_duplicates(anna):
    a = anna.post("/api/todos", json={"title": "Zahnarzt Termin vereinbaren"}).json()
    anna.post("/api/todos", json={"title": "Milch kaufen"})
    b = anna.post("/api/todos", json={"title": "Termin beim Zahnarzt vereinbaren"}).json()
    r = anna.post("/api/ai/duplicates", json={"title": "Zahnarzttermin vereinbaren!", "exclude_id": b["id"]}).json()
    assert [d["id"] for d in r["duplicates"]] == [a["id"]]
    assert anna.post("/api/ai/duplicates", json={"title": "Auto waschen"}).json()["duplicates"] == []
    pairs = anna.get("/api/ai/duplicates/all").json()["pairs"]
    assert len(pairs) == 1 and {pairs[0]["a"]["id"], pairs[0]["b"]["id"]} == {a["id"], b["id"]}
    assert ai_tools.similar("Milch kaufen", "Milch kaufen ") == 1.0 and ai_tools.similar("Milch", "Brot") < 0.5


def test_suggest_tags_and_list(anna, monkeypatch):
    lst = anna.post("/api/lists", json={"name": "Arbeit"}).json()
    anna.post("/api/todos", json={"title": "x", "tags": ["büro"]})
    t = anna.post("/api/todos", json={"title": "Präsentation vorbereiten", "tags": ["dringend"]}).json()

    async def fake(model, messages):
        assert "büro" in messages[0]["content"] and "arbeit" in messages[0]["content"]
        return {"tags": ["Büro", "dringend", "ungültig tag!", "Meeting Prep"], "list": "Arbeit"}

    monkeypatch.setattr(ollama, "chat_json", fake)
    r = anna.post("/api/ai/suggest", json={"todo_id": t["id"]}).json()
    assert r == {"tags": ["büro", "meeting-prep"], "list_id": lst["id"]}
    assert anna.post("/api/ai/suggest", json={"todo_id": 99999}).status_code == 404


def test_vector_norm():
    v = ai_tools._norm([3.0, 4.0])
    assert math.isclose(v[0], 0.6, rel_tol=1e-6) and math.isclose(v[1], 0.8, rel_tol=1e-6)


def test_ai_times_respect_dst(anna, monkeypatch):
    """Im Oktober (Sommerzeit, Offset -120) vorgeschlagenes Datum im November (Winterzeit) bleibt 09:00 Ortszeit."""
    anna.put("/api/settings", json={"tz": "Europe/Berlin"})

    async def fake(model, messages):
        return {"reply": "", "actions": [{"type": "create", "title": "Steuer", "due_at": "2026-11-15T09:00"},
                                         {"type": "create", "title": "Sommer", "due_at": "2026-10-24T09:00"}]}

    monkeypatch.setattr(ollama, "chat_json", fake)
    acts = anna.post("/api/ai/interpret", json={"text": "x", "now_local": "2026-10-24T10:00", "tz_offset": -120}).json()["actions"]
    assert [a["due_at"] for a in acts] == ["2026-11-15T08:00:00Z", "2026-10-24T07:00:00Z"]
