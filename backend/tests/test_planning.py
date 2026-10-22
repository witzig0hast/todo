import pytest

from app import db
from tests.conftest import login, make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def approve(name):
    with db.session() as c:
        c.execute("UPDATE users SET status='approved' WHERE username = ?", (name,))


def switch(client, name):
    client.post("/api/auth/logout")
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    login(client, name)


@pytest.fixture()
def two(client):
    make_user(client, "alice")
    client.cookies.clear()
    make_user(client, "bob")
    approve("bob")
    make_user(client, "carol")
    approve("carol")
    login(client, "alice")
    return client


# ------------------------------------------------------------------ Geteilte Listen
def test_shared_list_visibility_and_editing(two):
    c = two
    lst = c.post("/api/lists", json={"name": "Einkauf"}).json()
    c.post("/api/todos", json={"title": "Milch", "list_id": lst["id"]})
    private = c.post("/api/todos", json={"title": "Geheim"}).json()
    assert c.post(f"/api/lists/{lst['id']}/members", json={"username": "bob"}).status_code == 201
    assert c.post(f"/api/lists/{lst['id']}/members", json={"username": "gibtsnicht"}).status_code == 404
    assert c.post(f"/api/lists/{lst['id']}/members", json={"username": "alice"}).status_code == 404  # nicht sich selbst
    assert c.get("/api/lists").json()["lists"][0]["members"] == ["bob"]
    switch(c, "bob")
    lists = c.get("/api/lists").json()["lists"]
    assert [(l["name"], l["mine"], l["owner"]) for l in lists] == [("Einkauf", False, "alice")]
    titles = [t["title"] for t in c.get("/api/todos").json()["todos"]]
    assert titles == ["Milch"]  # nicht "Geheim"
    milk = c.get("/api/todos").json()["todos"][0]
    assert c.patch(f"/api/todos/{milk['id']}", json={"done": True}).status_code == 200
    bread = c.post("/api/todos", json={"title": "Brot", "list_id": lst["id"]}).json()
    assert c.patch(f"/api/todos/{private['id']}", json={"done": True}).status_code == 404
    assert c.delete(f"/api/todos/{private['id']}").status_code == 404
    assert c.patch(f"/api/lists/{lst['id']}", json={"name": "Gekapert"}).status_code == 404  # nur Besitzerin
    assert c.delete(f"/api/lists/{lst['id']}").status_code == 404
    assert c.post(f"/api/lists/{lst['id']}/members", json={"username": "carol"}).status_code == 404
    switch(c, "alice")
    assert {t["title"]: t["done"] for t in c.get("/api/todos").json()["todos"]} == {"Milch": True, "Brot": False, "Geheim": False}
    # Carol sieht nichts
    switch(c, "carol")
    assert c.get("/api/todos").json()["todos"] == [] and c.get("/api/lists").json()["lists"] == []
    assert c.patch(f"/api/todos/{bread['id']}", json={"title": "x"}).status_code == 404
    assert c.post("/api/todos", json={"title": "x", "list_id": lst["id"]}).status_code == 404


def test_leave_and_remove_member(two):
    c = two
    lst = c.post("/api/lists", json={"name": "Projekt"}).json()
    c.post(f"/api/lists/{lst['id']}/members", json={"username": "bob"})
    c.post(f"/api/lists/{lst['id']}/members", json={"username": "carol"})
    switch(c, "bob")
    assert c.delete(f"/api/lists/{lst['id']}/members/carol").status_code == 404  # nicht andere entfernen
    assert c.delete(f"/api/lists/{lst['id']}/members/bob").status_code == 204    # selbst verlassen
    assert c.get("/api/lists").json()["lists"] == []
    switch(c, "alice")
    assert c.delete(f"/api/lists/{lst['id']}/members/carol").status_code == 204
    assert c.get("/api/lists").json()["lists"][0]["members"] == []


def test_member_snooze_reminds_member(two):
    from app import push
    c = two
    lst = c.post("/api/lists", json={"name": "L"}).json()
    t = c.post("/api/todos", json={"title": "Gemeinsam", "list_id": lst["id"]}).json()
    c.post(f"/api/lists/{lst['id']}/members", json={"username": "bob"})
    switch(c, "bob")
    assert c.post(f"/api/todos/{t['id']}/snooze", json={"minutes": 5}).status_code == 200
    with db.session() as conn:
        bob = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()["id"]
        conn.execute("UPDATE reminders SET remind_at = '2000-01-01T00:00:00Z' WHERE offset_min IS NULL")
    sent = []
    import app.push as p
    orig = p._send_sync
    p._send_sync = lambda ids, payload: sent.append(ids)
    try:
        push._check_due()
    finally:
        p._send_sync = orig
    assert sent == [[bob]]


# ------------------------------------------------------------------ Anhänge
def test_attachments_upload_types_and_access(two):
    c = two
    t = c.post("/api/todos", json={"title": "Rechnung"}).json()
    up = lambda data, name="a.png": c.post(f"/api/todos/{t['id']}/attachments", content=data, headers={"X-Filename": name})
    r = up(PNG, "Rechnung%20M%C3%A4rz.png")
    assert r.status_code == 201 and r.json()["mime"] == "image/png" and r.json()["filename"] == "Rechnung März.png"
    assert up(b"%PDF-1.7 ...", "x.pdf").json()["mime"] == "application/pdf"
    assert up("Notiz äöü".encode(), "notiz.txt").json()["mime"] == "text/plain"
    assert up(b"<html><script>alert(1)</script></html>", "x.txt").status_code == 415
    assert up(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "x.svg").status_code == 415
    assert up(b"MZ\x90\x00\x03\x00\x00\x00\xff\xfe", "x.exe").status_code == 415
    assert up(b"", "leer").status_code == 422
    assert up(b"x", "../../etc/passwd").json()["filename"] == "passwd"
    files = c.get(f"/api/todos/{t['id']}/attachments").json()["attachments"]
    assert len(files) == 4
    dl = c.get(files[0]["url"])
    assert dl.status_code == 200 and dl.content == PNG and "sandbox" in dl.headers["content-security-policy"]
    assert dl.headers["x-content-type-options"] == "nosniff" and dl.headers["content-disposition"].startswith("inline")
    txt = c.get(files[2]["url"])
    assert txt.headers["content-disposition"].startswith("attachment")
    # andere Benutzer kommen nicht dran
    switch(c, "bob")
    assert c.get(files[0]["url"]).status_code == 404
    assert c.post(f"/api/todos/{t['id']}/attachments", content=PNG).status_code == 404
    switch(c, "alice")
    assert c.delete(files[0]["url"]).status_code == 204
    assert c.get(files[0]["url"]).status_code == 404


def test_attachment_size_limit_and_cleanup(two, monkeypatch):
    from app import attachments, config
    c = two
    t = c.post("/api/todos", json={"title": "Groß"}).json()
    monkeypatch.setattr(attachments, "MAX_FILE", 100)
    assert c.post(f"/api/todos/{t['id']}/attachments", content=PNG + b"\x00" * 200).status_code == 413
    monkeypatch.setattr(attachments, "MAX_FILE", 10 * 1024 * 1024)
    a = c.post(f"/api/todos/{t['id']}/attachments", content=PNG).json()
    with db.session() as conn:
        stored = conn.execute("SELECT stored_name FROM attachments WHERE id = ?", (a["id"],)).fetchone()["stored_name"]
    path = config.DATA_DIR / "attachments" / stored
    assert path.exists()
    c.delete(f"/api/todos/{t['id']}")  # Aufgabe löschen entfernt auch die Datei
    assert not path.exists()


# ------------------------------------------------------------------ Kalender-Feed
def test_ics_feed(two):
    c = two
    c.post("/api/todos", json={"title": "Zahnarzt; Kontrolle, jährlich", "due_at": "2030-03-01T08:00:00Z", "priority": 3,
                               "notes": "Zeile 1\nZeile 2", "tags": ["gesundheit"]})
    c.post("/api/todos", json={"title": "Ohne Datum"})
    assert c.get("/api/calendar/feed").json() == {"enabled": False}
    url = c.post("/api/calendar/feed").json()["url"]
    path = url.split("testserver", 1)[1]
    anon = c.__class__(c.app)
    r = anon.get(path)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert "SUMMARY:Zahnarzt\; Kontrolle\\, jährlich" in body and "DTSTART:20300301T080000Z" in body
    assert "DESCRIPTION:Zeile 1\\nZeile 2" in body and "PRIORITY:1" in body and "Ohne Datum" not in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    # neuer Link -> alter ungültig; abschalten
    url2 = c.post("/api/calendar/feed").json()["url"]
    assert anon.get(path).status_code == 404 and anon.get(url2.split("testserver", 1)[1]).status_code == 200
    c.delete("/api/calendar/feed")
    assert anon.get(url2.split("testserver", 1)[1]).status_code == 404
