import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["COOKIE_SECURE"] = "false"
os.environ["FRONTEND_DIR"] = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, security  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    db.init_db()
    with db.session() as c:
        for t in ("invites", "todo_history", "comments", "todo_deps", "templates", "time_entries", "trash", "webauthn_challenges", "passkeys", "login_tickets", "recovery_codes", "attachments", "list_members", "mail_accounts", "rules", "saved_filters", "reminders", "device_messages", "devices", "identities", "oidc_states", "oidc_pending", "audit_log", "messages", "agents", "todos", "lists", "sessions", "push_subscriptions", "users"):
            c.execute(f"DELETE FROM {t}")
    security.limiter.clear()
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def make_user(client, name, pw="passwort-12345"):
    r = client.post("/api/auth/register", json={"username": name, "password": pw})
    assert r.status_code == 201, r.text
    return r.json()


def login(client, name, pw="passwort-12345"):
    r = client.post("/api/auth/login", json={"username": name, "password": pw})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r.json()
