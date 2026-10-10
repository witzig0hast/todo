import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','blocked')),
  created_at TEXT NOT NULL,
  approved_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  user_agent TEXT
);
CREATE TABLE IF NOT EXISTS lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#7c5cff',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  list_id INTEGER REFERENCES lists(id) ON DELETE SET NULL,
  parent_id INTEGER REFERENCES todos(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
  due_at TEXT,
  done INTEGER NOT NULL DEFAULT 0,
  done_at TEXT,
  reminded INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL DEFAULT 'user',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_todos_user ON todos(user_id, done);
CREATE INDEX IF NOT EXISTS idx_todos_parent ON todos(parent_id);
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL COLLATE NOCASE,
  description TEXT,
  key_hash TEXT NOT NULL UNIQUE,
  key_prefix TEXT NOT NULL,
  scopes TEXT NOT NULL DEFAULT 'send',
  created_at TEXT NOT NULL,
  last_seen_at TEXT,
  UNIQUE (user_id, name)
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  from_label TEXT NOT NULL,
  to_label TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('text','task')),
  content TEXT,
  task_type TEXT,
  payload TEXT,
  status TEXT NOT NULL,
  result TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(user_id, to_label, status);
CREATE TABLE IF NOT EXISTS push_subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL UNIQUE,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_settings (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  ollama_model TEXT
);
CREATE TABLE IF NOT EXISTS identities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  subject TEXT NOT NULL,
  email TEXT,
  created_at TEXT NOT NULL,
  last_login_at TEXT,
  UNIQUE (provider, subject)
);
CREATE TABLE IF NOT EXISTS oidc_states (
  state TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  nonce TEXT NOT NULL,
  verifier TEXT NOT NULL,
  link_user_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_pending (
  token_hash TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  subject TEXT NOT NULL,
  email TEXT,
  claims TEXT NOT NULL,
  is_admin_group INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  user_id INTEGER,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT,
  ip TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "has_password" not in cols:  # Migration: SSO-Konten haben zunächst kein lokales Passwort
            conn.execute("ALTER TABLE users ADD COLUMN has_password INTEGER NOT NULL DEFAULT 1")


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI-Dependency: eine Verbindung pro Request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def audit(conn: sqlite3.Connection, actor: str, action: str, detail: str | None = None,
          user_id: int | None = None, ip: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (at, user_id, actor, action, detail, ip) VALUES (?,?,?,?,?,?)",
        (now(), user_id, actor, action, detail, ip),
    )
