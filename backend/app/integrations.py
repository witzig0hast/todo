"""Persönliche API-Tokens + darauf aufbauende Schnittstellen:
- /api/v1/...: schlichte REST-API (z. B. Home-Assistant-Sensor, Schnelleingabe per Sprachassistent, Skripte)
- /api/mcp:    MCP-Server (Model Context Protocol, Streamable HTTP, zustandslos) für Claude & andere KI-Agenten.
Tokens: „tdk_…“, nur als SHA-256-Hash gespeichert, Rechte read und/oder write, jederzeit widerrufbar."""
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ValidationError

from .db import get_db, now
from .recurrence import FMT, user_tz
from .security import Auth, enforce_rate, get_auth, sha256
from .todos import QuickIn, TodoPatch, api_quick_create, get_todo, list_todos, update_todo

router = APIRouter(prefix="/api", tags=["integrations"])
MAX_TOKENS = 20


# ------------------------------------------------------------------ Tokens verwalten (angemeldet, Cookie)
class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[Literal["read", "write"]] = Field(default_factory=lambda: ["read"], min_length=1)


@router.get("/tokens")
def list_tokens(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, name, prefix, scopes, created_at, last_used_at FROM api_tokens WHERE user_id = ? ORDER BY id DESC", (auth.id,))
    return {"tokens": [{**dict(r), "scopes": r["scopes"].split(",")} for r in rows]}


@router.post("/tokens", status_code=201)
def create_token(data: TokenIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM api_tokens WHERE user_id = ?", (auth.id,)).fetchone()[0] >= MAX_TOKENS:
        raise HTTPException(422, f"Maximal {MAX_TOKENS} Tokens.")
    raw = "tdk_" + secrets.token_urlsafe(32)
    scopes = ",".join(sorted(set(data.scopes)))
    cur = conn.execute("INSERT INTO api_tokens (user_id, name, token_hash, prefix, scopes, created_at) VALUES (?,?,?,?,?,?)",
                       (auth.id, data.name.strip(), sha256(raw), raw[:10], scopes, now()))
    return {"id": cur.lastrowid, "name": data.name.strip(), "scopes": scopes.split(","), "token": raw}


@router.delete("/tokens/{token_id}", status_code=204)
def delete_token(token_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("DELETE FROM api_tokens WHERE id = ? AND user_id = ?", (token_id, auth.id)).rowcount == 0:
        raise HTTPException(404, "Token nicht gefunden.")


# ------------------------------------------------------------------ Token-Anmeldung
class TokenUser:
    def __init__(self, user: sqlite3.Row, scopes: set[str], name: str) -> None:
        self.user, self.scopes, self.name = user, scopes, name

    @property
    def id(self) -> int:
        return self.user["id"]

    def need(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(403, f"Token hat kein Recht „{scope}“.")


def get_token_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> TokenUser:
    header = request.headers.get("authorization", "")
    raw = header[7:].strip() if header.lower().startswith("bearer ") else request.headers.get("x-api-token", "")
    if not raw.startswith("tdk_"):
        raise HTTPException(401, "API-Token fehlt (Header: Authorization: Bearer tdk_…).", headers={"WWW-Authenticate": "Bearer"})
    row = conn.execute("SELECT t.id AS token_id, t.scopes, t.name AS token_name, t.last_used_at, u.* FROM api_tokens t "
                       "JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?", (sha256(raw),)).fetchone()
    if row is None or row["status"] != "approved":
        raise HTTPException(401, "Ungültiges API-Token.", headers={"WWW-Authenticate": "Bearer"})
    enforce_rate(f"token:{row['token_id']}", 120, 60)
    if not row["last_used_at"] or row["last_used_at"][:16] != now()[:16]:
        conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (now(), row["token_id"]))
    return TokenUser(row, set(row["scopes"].split(",")), row["token_name"])


# ------------------------------------------------------------------ REST v1 (Home Assistant, Skripte)
def _short(t: dict) -> dict:
    return {k: t.get(k) for k in ("id", "title", "due_at", "priority", "done", "tags", "list_id", "notes")}


def summary(conn: sqlite3.Connection, user_id: int) -> dict:
    local = datetime.now(timezone.utc).astimezone(user_tz(conn, user_id))
    end = local.replace(hour=23, minute=59, second=59).astimezone(timezone.utc).strftime(FMT)
    current = now()
    todos = [t for t in list_todos(conn, user_id, done=False, limit=2000) if not t["parent_id"]]
    today = sorted([t for t in todos if t["due_at"] and t["due_at"] <= end], key=lambda t: t["due_at"])
    overdue = [t for t in today if t["due_at"] < current]
    nxt = sorted([t for t in todos if t["due_at"] and t["due_at"] >= current], key=lambda t: t["due_at"])
    return {"open": len(todos), "today": len(today), "overdue": len(overdue),
            "next": _short(nxt[0]) if nxt else None, "today_titles": [t["title"] for t in today[:10]]}


@router.get("/v1/summary")
def v1_summary(tu: TokenUser = Depends(get_token_user), conn: sqlite3.Connection = Depends(get_db)):
    tu.need("read")
    return summary(conn, tu.id)


@router.get("/v1/todos")
def v1_todos(due: Literal["all", "today", "overdue"] = "all", tu: TokenUser = Depends(get_token_user),
             conn: sqlite3.Connection = Depends(get_db)):
    tu.need("read")
    return {"todos": [_short(t) for t in _filtered(conn, tu.id, due)]}


def _filtered(conn: sqlite3.Connection, user_id: int, due: str, q: str | None = None, limit: int = 200) -> list[dict]:
    todos = [t for t in list_todos(conn, user_id, done=False, limit=2000, q=q or None) if not t["parent_id"]]
    if due != "all":
        local = datetime.now(timezone.utc).astimezone(user_tz(conn, user_id))
        end = local.replace(hour=23, minute=59, second=59).astimezone(timezone.utc).strftime(FMT)
        bound = now() if due == "overdue" else end
        todos = [t for t in todos if t["due_at"] and t["due_at"] <= bound]
    return todos[:limit]


class V1Quick(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/v1/quick", status_code=201)
def v1_quick(data: V1Quick, tu: TokenUser = Depends(get_token_user), conn: sqlite3.Connection = Depends(get_db)):
    """Schnelleingabe wie in der App: „morgen 9 Uhr Müll rausbringen #haushalt“ (z. B. aus Home Assistant Assist)."""
    tu.need("write")
    return _short(_create_quick(conn, tu, data.text))


def _create_quick(conn: sqlite3.Connection, tu: TokenUser, text: str) -> dict:
    class _A:  # api_quick_create erwartet ein Auth-ähnliches Objekt
        id = tu.id

    return api_quick_create(QuickIn(text=text), _A(), conn)


@router.post("/v1/todos/{todo_id}/done")
def v1_done(todo_id: int, tu: TokenUser = Depends(get_token_user), conn: sqlite3.Connection = Depends(get_db)):
    tu.need("write")
    return _short(update_todo(conn, tu.id, todo_id, {"done": True}, actor=f"{tu.user['username']} ({tu.name})"))


# ------------------------------------------------------------------ MCP (Model Context Protocol, Streamable HTTP)
MCP_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
TOOLS = [
    {"name": "list_todos", "description": "Offene Aufgaben des Nutzers auflisten (optional nur heute fällige/überfällige oder mit Suchbegriff).",
     "inputSchema": {"type": "object", "properties": {
         "due": {"type": "string", "enum": ["all", "today", "overdue"], "default": "all"},
         "query": {"type": "string", "description": "Suchbegriff in Titel/Notizen/Tags"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}}}},
    {"name": "create_todo", "description": "Aufgabe anlegen. Der Text wird wie in der App-Schnelleingabe ausgewertet: "
                                           "„morgen 15 Uhr Zahnarzt #privat !!“, „jeden Montag Müll @haushalt“.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string", "maxLength": 300},
                                                                             "notes": {"type": "string", "maxLength": 5000}}}},
    {"name": "complete_todo", "description": "Aufgabe als erledigt markieren.",
     "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}},
    {"name": "update_todo", "description": "Aufgabe ändern (Titel, Notizen, Fälligkeit als ISO-8601 mit Zeitzone, Priorität 0-3, Tags).",
     "inputSchema": {"type": "object", "required": ["id"], "properties": {
         "id": {"type": "integer"}, "title": {"type": "string"}, "notes": {"type": "string"},
         "due_at": {"type": ["string", "null"]}, "priority": {"type": "integer", "minimum": 0, "maximum": 3},
         "tags": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "list_lists", "description": "Listen und Projekte des Nutzers.", "inputSchema": {"type": "object", "properties": {}}},
]
WRITE_TOOLS = {"create_todo", "complete_todo", "update_todo"}


def _rpc_error(id_, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _text(obj: object, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, indent=1) if not isinstance(obj, str) else obj}],
            "isError": error}


def _call(conn: sqlite3.Connection, tu: TokenUser, name: str, args: dict) -> dict:
    if name in WRITE_TOOLS and "write" not in tu.scopes:
        return _text("Dieses Token darf nur lesen.", True)
    if "read" not in tu.scopes and name in ("list_todos", "list_lists"):
        return _text("Dieses Token darf nicht lesen.", True)
    actor = f"{tu.user['username']} ({tu.name})"
    try:
        if name == "list_todos":
            items = _filtered(conn, tu.id, str(args.get("due") or "all"), str(args.get("query") or "")[:100] or None,
                              max(1, min(200, int(args.get("limit") or 50))))
            return _text({"todos": [_short(t) for t in items]})
        if name == "create_todo":
            t = _create_quick(conn, tu, str(args.get("text") or "")[:300])
            if args.get("notes"):
                t = update_todo(conn, tu.id, t["id"], {"notes": str(args["notes"])[:5000]}, actor=actor)
            return _text({"created": _short(t)})
        if name == "complete_todo":
            return _text({"done": _short(update_todo(conn, tu.id, int(args["id"]), {"done": True}, actor=actor))})
        if name == "update_todo":
            fields = {k: args[k] for k in ("title", "notes", "due_at", "priority", "tags") if k in args}
            patch = TodoPatch(**fields).model_dump(exclude_unset=True)
            get_todo(conn, tu.id, int(args["id"]))
            return _text({"updated": _short(update_todo(conn, tu.id, int(args["id"]), patch, actor=actor))})
        if name == "list_lists":
            rows = conn.execute("SELECT id, name, kind FROM lists WHERE user_id = :u OR id IN "
                                "(SELECT list_id FROM list_members WHERE user_id = :u) ORDER BY name", {"u": tu.id})
            return _text({"lists": [dict(r) for r in rows]})
    except HTTPException as exc:
        return _text(str(exc.detail), True)
    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        return _text(f"Ungültige Eingabe: {exc}", True)
    return _text(f"Unbekanntes Werkzeug: {name}", True)


def _handle(conn: sqlite3.Connection, tu: TokenUser, msg: object) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    id_, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if id_ is None:  # Benachrichtigung (z. B. notifications/initialized): keine Antwort
        return None
    if method == "initialize":
        version = params.get("protocolVersion") if params.get("protocolVersion") in MCP_VERSIONS else MCP_VERSIONS[0]
        return {"jsonrpc": "2.0", "id": id_, "result": {
            "protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "todo", "title": "Todo", "version": "1.0"},
            "instructions": "Aufgabenverwaltung des Nutzers. Zeiten sind UTC (ISO 8601). Lege Aufgaben bevorzugt mit "
                            "create_todo und natürlichem deutschem Text an."}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": id_, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": id_, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(args, dict):
            return _rpc_error(id_, -32602, "Invalid params")
        return {"jsonrpc": "2.0", "id": id_, "result": _call(conn, tu, name, args)}
    return _rpc_error(id_, -32601, f"Method not found: {method}")


@router.post("/mcp")
async def mcp(request: Request, tu: TokenUser = Depends(get_token_user), conn: sqlite3.Connection = Depends(get_db)):
    origin = request.headers.get("origin")
    if origin and origin.split("://", 1)[-1] != request.headers.get("host", ""):
        raise HTTPException(403, "Fremde Origin.")  # Schutz vor DNS-Rebinding aus dem Browser
    try:
        body = json.loads(await request.body() or b"null")
    except ValueError:
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
    if isinstance(body, list):
        out = [r for r in (_handle(conn, tu, m) for m in body[:20]) if r is not None]
        return JSONResponse(out) if out else Response(status_code=202)
    res = _handle(conn, tu, body)
    return JSONResponse(res) if res is not None else Response(status_code=202)


@router.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})

