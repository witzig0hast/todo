"""Paket 8: Kanban-Status, Projekte, Abhängigkeiten, Zuweisen, Kommentare/Erwähnungen, Verlauf, Einladungen."""
import pytest

from app import push
from tests.conftest import login, make_user
from tests.test_planning import approve, switch


@pytest.fixture()
def team(client, monkeypatch):
    sent = []
    monkeypatch.setattr(push, "notify_threadsafe", lambda users, title, body, url="/": sent.append((sorted(users), title, body)))
    make_user(client, "anna")
    client.cookies.clear()
    for n in ("ben", "cara"):
        make_user(client, n)
        approve(n)
        client.cookies.clear()
    login(client, "anna")
    lst = client.post("/api/lists", json={"name": "Umzug", "kind": "project", "due_at": "2030-05-01T10:00:00Z"}).json()
    client.post(f"/api/lists/{lst['id']}/members", json={"username": "ben"})
    sent.clear()
    return client, lst, sent


def uid(client, name):
    return {p["username"]: p["id"] for p in client.get("/api/people").json()["people"]}[name]


def test_project_list_and_stage(team):
    c, lst, _ = team
    got = [x for x in c.get("/api/lists").json()["lists"] if x["id"] == lst["id"]][0]
    assert got["kind"] == "project" and got["due_at"] == "2030-05-01T10:00:00Z"
    c.patch(f"/api/lists/{lst['id']}", json={"due_at": None})
    assert [x for x in c.get("/api/lists").json()["lists"] if x["id"] == lst["id"]][0]["due_at"] is None
    t = c.post("/api/todos", json={"title": "Kisten", "list_id": lst["id"]}).json()
    assert t["stage"] == "todo" and t["blocked_by"] == [] and t["comment_count"] == 0
    assert c.patch(f"/api/todos/{t['id']}", json={"stage": "doing"}).json()["stage"] == "doing"
    c.patch(f"/api/todos/{t['id']}", json={"done": True})
    back = c.patch(f"/api/todos/{t['id']}", json={"stage": "doing"}).json()  # vom Board aus „Erledigt“ zurückziehen
    assert back["done"] is False and back["stage"] == "doing"
    assert c.patch(f"/api/todos/{t['id']}", json={"stage": "fertig"}).status_code == 422


def test_assign_only_members_and_notify(team):
    c, lst, sent = team
    t = c.post("/api/todos", json={"title": "Kisten packen", "list_id": lst["id"]}).json()
    assert c.patch(f"/api/todos/{t['id']}", json={"assignee": "cara"}).status_code == 422  # nicht in der Liste
    r = c.patch(f"/api/todos/{t['id']}", json={"assignee": "Ben"}).json()
    assert r["assignee_id"] == uid(c, "ben")
    assert sent[-1][0] == [uid(c, "ben")] and sent[-1][1] == "Neue Aufgabe für dich"
    private = c.post("/api/todos", json={"title": "Privat"}).json()
    assert c.patch(f"/api/todos/{private['id']}", json={"assignee": "ben"}).status_code == 422
    assert c.patch(f"/api/todos/{private['id']}", json={"assignee": "anna"}).status_code == 200
    assert c.patch(f"/api/todos/{t['id']}", json={"assignee": ""}).json()["assignee_id"] is None
    names = [p["username"] for p in c.get("/api/people").json()["people"]]
    assert names == ["anna", "ben"]  # cara teilt nichts mit anna


def test_dependencies_cycle_and_unblock(team):
    c, lst, sent = team
    a = c.post("/api/todos", json={"title": "Kartons kaufen", "list_id": lst["id"]}).json()
    b = c.post("/api/todos", json={"title": "Packen", "list_id": lst["id"]}).json()
    x = c.post("/api/todos", json={"title": "Transporter", "list_id": lst["id"]}).json()
    assert c.post(f"/api/todos/{b['id']}/deps", json={"blocked_by": a["id"]}).json()["blocked_by"] == [a["id"]]
    c.post(f"/api/todos/{x['id']}/deps", json={"blocked_by": b["id"]})
    assert c.post(f"/api/todos/{a['id']}/deps", json={"blocked_by": x["id"]}).status_code == 422  # Kreis a<-x<-b<-a
    assert c.post(f"/api/todos/{a['id']}/deps", json={"blocked_by": a["id"]}).status_code == 422
    c.patch(f"/api/todos/{b['id']}", json={"assignee": "ben"})
    sent.clear()
    c.patch(f"/api/todos/{a['id']}", json={"done": True})
    assert sent == [([uid(c, "ben")], "Kann losgehen", "Packen")]
    todos = {t["id"]: t for t in c.get("/api/todos").json()["todos"]}
    assert todos[x["id"]]["blocked_by"] == [b["id"]]
    assert c.delete(f"/api/todos/{x['id']}/deps/{b['id']}").json()["blocked_by"] == []
    assert c.delete(f"/api/todos/{x['id']}/deps/{b['id']}").status_code == 404
    switch(c, "cara")  # fremd: weder lesen noch verknüpfen
    own = c.post("/api/todos", json={"title": "Caras"}).json()
    assert c.post(f"/api/todos/{own['id']}/deps", json={"blocked_by": a["id"]}).status_code == 404


def test_comments_mentions_and_history(team):
    c, lst, sent = team
    t = c.post("/api/todos", json={"title": "Küche", "list_id": lst["id"]}).json()
    c.patch(f"/api/todos/{t['id']}", json={"title": "Küche abbauen", "due_at": "2030-04-01T08:00:00Z", "assignee": "ben"})
    sent.clear()
    r = c.post(f"/api/todos/{t['id']}/comments", json={"body": "@ben kannst du das? @cara auch"}).json()
    assert r["author"] == "anna" and r["mine"]
    assert sent == [([uid(c, "ben")], "anna hat dich erwähnt", "Küche abbauen: @ben kannst du das? @cara auch")]  # cara sieht die Liste nicht
    switch(c, "ben")
    sent.clear()
    c.post(f"/api/todos/{t['id']}/comments", json={"body": "Mach ich"})
    assert sent == [([uid(c, "anna")], "Kommentar von ben", "Küche abbauen: Mach ich")]  # an die Besitzerin, nicht an ben selbst
    comments = c.get(f"/api/todos/{t['id']}/comments").json()["comments"]
    assert [x["author"] for x in comments] == ["anna", "ben"] and comments[0]["mine"] is False
    assert c.delete(f"/api/comments/{comments[0]['id']}").status_code == 404  # fremder Kommentar
    assert c.get("/api/todos").json()["todos"][0]["comment_count"] == 2
    hist = c.get(f"/api/todos/{t['id']}/history").json()["history"]
    actions = [h["action"] for h in hist]
    assert actions[-1] == "created" and {"title", "due_at", "assignee"} <= set(actions)
    assert [h for h in hist if h["action"] == "title"][0]["detail"] == {"from": "Küche", "to": "Küche abbauen"}
    switch(c, "cara")
    assert c.get(f"/api/todos/{t['id']}/comments").status_code == 404
    assert c.get(f"/api/todos/{t['id']}/history").status_code == 404


def test_trash_keeps_comments_and_deps(team):
    c, lst, _ = team
    a = c.post("/api/todos", json={"title": "A", "list_id": lst["id"]}).json()
    b = c.post("/api/todos", json={"title": "B", "list_id": lst["id"]}).json()
    c.post(f"/api/todos/{b['id']}/deps", json={"blocked_by": a["id"]})
    c.post(f"/api/todos/{b['id']}/comments", json={"body": "Hallo"})
    tid = c.delete(f"/api/todos/{b['id']}").json()["trash_id"]
    c.post(f"/api/trash/{tid}/restore")
    rb = [t for t in c.get("/api/todos").json()["todos"] if t["id"] == b["id"]][0]
    assert rb["blocked_by"] == [a["id"]] and rb["comment_count"] == 1
    # Blocker gelöscht -> Wiederherstellen der abhängigen Aufgabe klappt trotzdem (Abhängigkeit entfällt)
    tid_b = c.delete(f"/api/todos/{b['id']}").json()["trash_id"]
    c.delete(f"/api/todos/{a['id']}")
    c.post(f"/api/trash/{tid_b}/restore")
    rb = [t for t in c.get("/api/todos").json()["todos"] if t["id"] == b["id"]][0]
    assert rb["blocked_by"] == []


def test_invites(client):
    make_user(client, "admin")
    login(client, "admin")
    inv = client.post("/api/admin/invites", json={"note": "Familie", "days": 3, "max_uses": 1}).json()
    token = inv["url"].split("invite=")[1]
    assert client.get("/api/admin/invites").json()["invites"][0]["active"] is True
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert client.get(f"/api/auth/invite/{token}").json() == {"valid": True, "note": "Familie", "by": "admin"}
    assert client.get("/api/auth/invite/falsch").json() == {"valid": False}
    r = client.post("/api/auth/register", json={"username": "oma", "password": "geheim-12345", "invite": token})
    assert r.status_code == 201 and r.json()["status"] == "approved"
    assert client.get("/api/auth/me").json()["user"]["username"] == "oma"  # direkt angemeldet
    client.cookies.clear()
    r = client.post("/api/auth/register", json={"username": "opa", "password": "geheim-12345", "invite": token})
    assert r.status_code == 400  # verbraucht
    assert client.post("/api/auth/register", json={"username": "opa", "password": "geheim-12345"}).json()["status"] == "pending"
    login(client, "oma", "geheim-12345")
    assert client.post("/api/admin/invites", json={}).status_code == 403
