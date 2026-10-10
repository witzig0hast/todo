import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from . import admin_api, ai_api, auth_api, bus, config, db, events, push, push_api, sso, todos

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
    limit = config.MAX_AUDIO_BYTES if request.url.path == "/api/voice/transcribe" else config.MAX_BODY_BYTES
    if declared and declared.isdigit() and int(declared) > limit:
        return JSONResponse({"detail": "Anfrage zu groß."}, status_code=413)
    response: Response = await call_next(request)
    h = response.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(), payment=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if config.COOKIE_SECURE:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


for module in (auth_api, sso, admin_api, todos, bus, ai_api, push_api):
    app.include_router(module.router)


@app.get("/sw.js")
def service_worker():
    return FileResponse(config.FRONTEND_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=config.FRONTEND_DIR), name="static")
