"""Paket 11 (Server-Seite): Widget-Daten, Schnellerfassung und Abhaken per Geräte-Token, App-Updates."""
from tests.conftest import login, make_user
from tests.test_planning import approve, switch

APK = b"PK\x03\x04" + b"\x00" * 2000 + b"AndroidManifest.xml" + b"\x00" * 100


def device(client):
    return client.post("/api/devices/register", json={"name": "Pixel", "platform": "android"}).json()


def test_widget_quick_done(client):
    make_user(client, "anna")
    login(client, "anna")
    client.put("/api/settings", json={"tz": "Europe/Berlin"})
    d = device(client)
    client.post("/api/todos", json={"title": "Überfällig", "due_at": "2001-01-01T08:00:00Z"})
    client.post("/api/todos", json={"title": "Irgendwann"})
    anon = client.__class__(client.app)
    h = {"Authorization": f"Bearer {d['token']}"}
    w = anon.get("/api/app/widget", headers=h).json()
    assert w["open"] == 2 and w["overdue"] == 1 and [i["title"] for i in w["items"]] == ["Überfällig", "Irgendwann"]
    assert w["items"][0]["overdue"] is True
    t = anon.post("/api/app/quick", headers=h, json={"text": "morgen Zahnarzt anrufen !!"}).json()
    assert t["title"] == "Zahnarzt anrufen" and t["due_at"]
    assert anon.post(f"/api/app/todos/{t['id']}/done", headers=h).json()["done"] is True
    assert anon.get("/api/app/widget").status_code == 401
    assert anon.get("/api/app/widget", headers={"Authorization": "Bearer tdv_falsch"}).status_code == 401
    hist = client.get(f"/api/todos/{t['id']}/history").json()["history"]
    assert hist[0]["actor"] == "Pixel (Widget)"


def test_android_update_distribution(client):
    make_user(client, "admin")
    client.cookies.clear()
    make_user(client, "bob")
    approve("bob")
    login(client, "admin")
    assert client.get("/api/app/android").json() == {"available": False}
    assert client.post("/api/app/android", params={"version_code": 5, "version_name": "1.0.5"}, content=b"kein apk").status_code == 415
    m = client.post("/api/app/android", params={"version_code": 5, "version_name": "1.0.5"}, content=APK).json()
    assert m["version_code"] == 5 and m["size"] == len(APK)
    assert client.post("/api/app/android", params={"version_code": 4, "version_name": "1.0.4"}, content=APK).status_code == 409
    # CI-Upload per Admin-Token
    tok = client.post("/api/tokens", json={"name": "CI", "scopes": ["write"]}).json()["token"]
    anon = client.__class__(client.app)
    r = anon.post("/api/app/android", params={"version_code": 6, "version_name": "1.0.6"}, content=APK, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201
    switch(client, "bob")
    d = device(client)
    meta = anon.get("/api/app/android", headers={"Authorization": f"Bearer {d['token']}"}).json()
    assert meta["available"] and meta["version_code"] == 6
    dl = anon.get("/api/app/android/download", headers={"Authorization": f"Bearer {d['token']}"})
    assert dl.status_code == 200 and dl.content == APK and dl.headers["content-type"] == "application/vnd.android.package-archive"
    assert client.post("/api/app/android", params={"version_code": 7, "version_name": "1.0.7"}, content=APK).status_code == 403
    bob_tok = client.post("/api/tokens", json={"name": "x", "scopes": ["write"]}).json()["token"]
    assert anon.post("/api/app/android", params={"version_code": 7, "version_name": "1.0.7"}, content=APK,
                     headers={"Authorization": f"Bearer {bob_tok}"}).status_code == 403
    assert anon.get("/api/app/android").status_code == 401
