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
CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'android',
  app_version TEXT,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS device_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  url TEXT,
  created_at TEXT NOT NULL,
  delivered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_dm_device ON device_messages(device_id, delivered_at);
CREATE TABLE IF NOT EXISTS oidc_pending (
  token_hash TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  subject TEXT NOT NULL,
  email TEXT,
  claims TEXT NOT NULL,
  is_admin_group INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remind_at TEXT NOT NULL,
  offset_min INTEGER,            -- Minuten vor Fälligkeit; NULL = geschlummert
  sent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(sent, remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_todo ON reminders(todo_id);
CREATE TABLE IF NOT EXISTS saved_filters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  match TEXT NOT NULL,
  action TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_fired_at TEXT,
  fire_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mail_accounts (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  host TEXT NOT NULL, port INTEGER NOT NULL, username TEXT NOT NULL, password_enc TEXT NOT NULL,
  folder TEXT NOT NULL DEFAULT 'INBOX', allowed_senders TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  last_check_at TEXT, last_error TEXT, imported INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS list_members (
  list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  added_at TEXT NOT NULL,
  PRIMARY KEY (list_id, user_id)
);
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  mime TEXT NOT NULL,
  size INTEGER NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_todo ON attachments(todo_id);
CREATE TABLE IF NOT EXISTS recovery_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL,
  used_at TEXT
);
CREATE TABLE IF NOT EXISTS login_tickets (
  ticket_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS passkeys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  credential_id TEXT NOT NULL UNIQUE,
  public_key BLOB NOT NULL,
  sign_count INTEGER NOT NULL DEFAULT 0,
  transports TEXT,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS webauthn_challenges (
  id TEXT PRIMARY KEY,
  user_id INTEGER,
  kind TEXT NOT NULL,
  challenge TEXT NOT NULL,
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


# Nachträglich hinzugefügte Spalten (Migration beim Start, idempotent)
COLUMNS = [
    ("users", "has_password", "INTEGER NOT NULL DEFAULT 1"),   # SSO-Konten haben zunächst kein lokales Passwort
    ("todos", "tags", "TEXT NOT NULL DEFAULT ''"),              # ",tag1,tag2,"
    ("todos", "recurrence", "TEXT"),                            # JSON, siehe todos.Recurrence
    ("todos", "remind_offsets", "TEXT NOT NULL DEFAULT '[0]'"),  # JSON-Liste: Minuten vor Fälligkeit
    ("device_messages", "todo_id", "INTEGER"),
    ("device_messages", "action_token", "TEXT"),
    ("user_settings", "tz", "TEXT"),
    ("devices", "quiet_start", "TEXT"),                         # "22:00" (lokale Zeit des Benutzers)
    ("devices", "quiet_end", "TEXT"),                           # "07:00"
    ("device_messages", "deliver_after", "TEXT"),               # während Ruhezeit zurückgehalten bis ...
    ("device_messages", "urgent", "INTEGER NOT NULL DEFAULT 0"),
    ("todos", "location", "TEXT"),                              # JSON {name, lat, lon, radius}
    ("agents", "webhook_hash", "TEXT"),                         # Webhook-Token (Hash) für eingehende Webhooks
    ("messages", "delivered_at", "TEXT"),                       # vom Empfänger-Agent abgeholt
    ("messages", "rules_fired", "TEXT"),                        # JSON-Liste ausgelöster Regeln
    ("device_messages", "bus_message_id", "INTEGER"),
    ("device_messages", "reply_token", "TEXT"),
    ("device_messages", "options", "TEXT"),                     # JSON-Liste Antwortoptionen
    ("user_settings", "summary_time", "TEXT"),                  # "08:00" = Morgen-Zusammenfassung, NULL = aus
    ("user_settings", "summary_sent_on", "TEXT"),               # "YYYY-MM-DD"
    ("user_settings", "ics_token_hash", "TEXT"),                # privater Kalender-Feed
    ("users", "totp_secret_enc", "TEXT"),                       # 2FA aktiv, wenn gesetzt (verschlüsselt)
    ("users", "totp_pending_enc", "TEXT"),                      # während der Einrichtung
    ("users", "totp_last_step", "INTEGER NOT NULL DEFAULT 0"),  # Schutz gegen Wiederverwendung eines Codes
    ("sessions", "last_seen_at", "TEXT"),
    ("sessions", "ip", "TEXT"),
]


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
        for table, column, ddl in COLUMNS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        # Einmalige Übernahme: offene, noch nicht erinnerte Aufgaben bekommen ihre Fälligkeits-Erinnerung
        conn.execute(
            "INSERT INTO reminders (todo_id, user_id, remind_at, offset_min) "
            "SELECT t.id, t.user_id, t.due_at, 0 FROM todos t WHERE t.done = 0 AND t.reminded = 0 AND t.due_at IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM reminders r WHERE r.todo_id = t.id) "
            "AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'migrated_reminders')")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('migrated_reminders', '1')")


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
