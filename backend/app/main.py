import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from . import (actions, admin_api, ai_api, assistant, attachments, auth_api, bus, calendar_feed, config, db, devices, events, mailin,
               push, push_api, rules, sso, todos)

logging.basicConfig(level=logging.INFO)

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; manifest-src 'self'; "
       "worker-src 'self'; media-src 'self' blob:")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    push.ensure_vapid()
    events.bind_loop(asyncio.get_running_loop())
    task = asyncio.create_task(push.reminder_loop())
    yield
    task.cancel()


app = FastAPI(title="Todo", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    declared = request.headers.get("content-length")
    big = request.url.path == "/api/voice/transcribe" or request.url.path.endswith("/attachments")
    limit = max(config.MAX_AUDIO_BYTES, 10 * 1024 * 1024) if big else config.MAX_BODY_BYTES
    if declared and declared.isdigit() and int(declared) > limit:
        return JSONResponse({"detail": "Anfrage zu groß."}, status_code=413)
    response: Response = await call_next(request)
    h = response.headers
    h.setdefault("Content-Security-Policy", CSP)
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(self), payment=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if config.COOKIE_SECURE:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    else:  # Oberfläche: Browser fragt bei jedem Aufruf per ETag nach (304 = fast gratis), damit Updates sofort ankommen
        h["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


for module in (auth_api, sso, admin_api, todos, attachments, calendar_feed, actions, bus, rules, devices, ai_api, assistant,
               mailin, push_api):
    app.include_router(module.router)


@app.get("/sw.js")
def service_worker():
    return FileResponse(config.FRONTEND_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


def _asset_version(name: str) -> str:
    return hashlib.sha256((config.FRONTEND_DIR / name).read_bytes()).hexdigest()[:10]


@app.get("/")
def index():
    """Startseite mit versionierten Asset-URLs (?v=<Prüfsumme>): Nach einem Update holt jeder Browser/CDN
    (z. B. Cloudflare) automatisch die neuen Dateien, ohne dass ein Cache geleert werden muss."""
    html = (config.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    for name in ("app.css", "app.js"):
        html = html.replace(f'"/{name}"', f'"/{name}?v={_asset_version(name)}"')
    return Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=config.FRONTEND_DIR), name="static")
