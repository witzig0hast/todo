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
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")   # Foto -> Aufgabe
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")           # semantische Suche (mehrsprachig)

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

# ---------------------------------------------------------------- SSO (OpenID Connect)
import json as _json  # noqa: E402

PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")  # z. B. https://todo.example.com (für die Redirect-URI)
LOCAL_AUTH_ENABLED = _bool("LOCAL_AUTH_ENABLED", True)

# E-Mail-Versand (Benachrichtigungskanal „E-Mail“, Login-Warnung); leer = aus
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "starttls").lower()  # starttls | ssl | none
# Benachrichtigungen an Server im internen Netz (ntfy/Gotify/Matrix im Heimnetz) erlauben: true = für alle,
# admins = nur für Admins (Standard), false = nie. Schützt vor Anfragen ins interne Netz über fremde Konten.
NOTIFY_PRIVATE_HOSTS = os.getenv("NOTIFY_PRIVATE_HOSTS", "admins").lower()
OIDC_AUTO_APPROVE = _bool("OIDC_AUTO_APPROVE", False)


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def load_oidc_providers() -> dict[str, dict]:
    """Entweder OIDC_PROVIDERS (JSON-Liste, mehrere Anbieter) oder die Kurzform OIDC_ISSUER/... (ein Anbieter)."""
    raw: list[dict] = []
    if os.getenv("OIDC_PROVIDERS"):
        raw = _json.loads(os.environ["OIDC_PROVIDERS"])
    elif os.getenv("OIDC_ISSUER"):
        raw = [{"id": os.getenv("OIDC_ID", "authentik"), "name": os.getenv("OIDC_NAME", "Authentik"),
                "issuer": os.environ["OIDC_ISSUER"], "client_id": os.getenv("OIDC_CLIENT_ID", ""),
                "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""), "scopes": os.getenv("OIDC_SCOPES"),
                "admin_groups": _split(os.getenv("OIDC_ADMIN_GROUPS"))}]
    out: dict[str, dict] = {}
    for p in raw:
        pid = str(p["id"]).lower()
        if not pid.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Ungültige OIDC-Provider-ID: {pid!r}")
        out[pid] = {
            "id": pid, "name": p.get("name") or pid, "issuer": p["issuer"].strip(), "client_id": p["client_id"],
            "client_secret": p.get("client_secret") or "", "scopes": p.get("scopes") or "openid profile email",
            "username_claim": p.get("username_claim") or "preferred_username",
            "groups_claim": p.get("groups_claim") or "groups",
            "admin_groups": p.get("admin_groups") or [],
            "auto_approve": bool(p.get("auto_approve", OIDC_AUTO_APPROVE)),
        }
    return out


OIDC_PROVIDERS = load_oidc_providers()
