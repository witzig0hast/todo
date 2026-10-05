import os
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "todo.db"
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend"))

# Cookies sind nur über HTTPS sicher - hinter nginx mit TLS immer true lassen.
COOKIE_SECURE = _bool("COOKIE_SECURE", True)
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "14"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))

WHISPER_HOST = os.getenv("WHISPER_HOST", "host.docker.internal")
WHISPER_PORT = int(os.getenv("WHISPER_PORT", "10300"))
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")
WHISPER_TIMEOUT = float(os.getenv("WHISPER_TIMEOUT", "60"))
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))
MAX_AUDIO_SECONDS = int(os.getenv("MAX_AUDIO_SECONDS", "120"))

VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")

LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(1024 * 1024)))
