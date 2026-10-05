"""Agent Bus: Nachrichten und Aufgaben zwischen dem Konto-Besitzer ("todo") und externen Agents."""
import asyncio
import json
import re
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import events, push, todos
from .db import audit, get_db, now
from .security import Auth, client_ip, get_agent, get_auth, new_agent_key

OWNER = "todo"
SCOPES = {"send", "todos:read", "todos:write"}
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

router = APIRouter(prefix="/api/agent-bus", tags=["agent-bus"])


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=512)
    scopes: list[str] = Field(default_factory=lambda: ["send"])

    @model_validator(mode="after")
    def _check(self) -> "AgentCreate":
        if not _NAME.match(self.name) or self.name.lower() == OWNER:
            raise ValueError(f"Ungültiger Name (erlaubt: Buchstaben, Ziffern, _ . -; '{OWNER}' ist reserviert).")
        if not set(self.scopes) <= SCOPES:
            raise ValueError("Unbekannter Scope.")
        return self


class MessageSend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str = Field(min_length=1, max_length=64)
    kind: Literal["text", "task"]
    content: str | None = Field(default=None, max_length=10000)
    task_type: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check(self) -> "MessageSend":
        if self.kind == "text" and not self.content:
            raise ValueError("content ist bei kind='text' erforderlich.")
        if self.kind == "task" and not self.task_type:
            raise ValueError("task_type ist bei kind='task' erforderlich.")
        if self.payload is not None and len(json.dumps(self.payload)) > 20000:
            raise ValueError("payload zu groß.")
        return self


class ResultIn(BaseModel):
    status: Literal["in_progress", "completed", "failed"]
    result: dict[str, Any] | None = None


def msg_out(r: sqlite3.Row) -> dict:
    d = dict(r)
    d.pop("user_id", None)
    for k in ("payload", "result"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def agent_out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "description": r["description"], "scopes": r["scopes"].split(","),
            "key_prefix": r["key_prefix"], "created_at": r["created_at"], "last_seen_at": r["last_seen_at"]}


# --------------------------------------------------------- eingebaute Todo-Tasks
def _run_todo_task(conn: sqlite3.Connection, user_id: int, agent: sqlite3.Row, task_type: str,
                   payload: dict) -> dict:
    scopes = set(agent["scopes"].split(","))

    def need(scope: str) -> None:
        if scope not in scopes:
            raise PermissionError(f"Scope '{scope}' fehlt für diesen Agent.")

    if task_type == "todo.create":
        need("todos:write")
        list_id = None
        if payload.get("list"):
            row = conn.execute("SELECT id FROM lists WHERE user_id = ? AND name = ? COLLATE NOCASE",
                               (user_id, str(payload["list"]))).fetchone()
            if row is None:
                raise LookupError(f"Liste '{payload['list']}' existiert nicht.")
            list_id = row["id"]
        data = todos.TodoIn(title=payload.get("title", ""), notes=payload.get("notes", ""),
                            priority=payload.get("priority", 0), due_at=payload.get("due_at"), list_id=list_id)
        return {"todo": todos.create_todo(conn, user_id, data, created_by=agent["name"])}
    if task_type == "todo.list":
        need("todos:read")
        done = payload.get("done")
        limit = min(int(payload.get("limit", 100)), 500)
        return {"todos": todos.list_todos(conn, user_id, done if isinstance(done, bool) else None, None, limit)}
    if task_type == "todo.complete":
        need("todos:write")
        return {"todo": todos.update_todo(conn, user_id, int(payload.get("id", 0)), {"done": True})}
    raise LookupError(f"Unbekannter Task-Typ '{task_type}'.")


def send_message(conn: sqlite3.Connection, user_id: int, from_agent: sqlite3.Row | None, data: MessageSend) -> dict:
    from_label = from_agent["name"] if from_agent else OWNER
    to = data.to.strip()
    ts = now()
    to_agent = None
    if to.lower() == OWNER:
        if from_agent is None:
            raise HTTPException(422, "Nachricht an sich selbst ist nicht möglich.")
        to_label = OWNER
    else:
        to_agent = conn.execute("SELECT * FROM agents WHERE user_id = ? AND name = ?", (user_id, to)).fetchone()
        if to_agent is None:
            raise HTTPException(404, "Empfänger nicht gefunden.")
        to_label = to_agent["name"]
    builtin = to_label == OWNER and data.kind == "task" and (data.task_type or "").startswith("todo.")
    if from_agent is not None and "send" not in from_agent["scopes"].split(",") and not builtin:
        raise HTTPException(403, "Scope 'send' fehlt für diesen Agent.")

    status = "sent" if data.kind == "text" else "pending"
    result = None
    if builtin and from_agent is not None:
        try:
            result, status = _run_todo_task(conn, user_id, from_agent, data.task_type, data.payload or {}), "completed"
        except PermissionError as exc:
            result, status = {"error": str(exc)}, "failed"
        except (LookupError, ValueError, TypeError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            result, status = {"error": str(detail)}, "failed"

    cur = conn.execute(
        "INSERT INTO messages (user_id, from_label, to_label, kind, content, task_type, payload, status, result,"
        " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, from_label, to_label, data.kind, data.content, data.task_type,
         json.dumps(data.payload) if data.payload is not None else None, status,
         json.dumps(result) if result is not None else None, ts, ts),
    )
    out = msg_out(conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone())
    events.publish("user", user_id, "bus", out)
    if to_agent is not None:
        events.publish("agent", to_agent["id"], "message", out)
    elif from_agent is not None:
        label = data.content if data.kind == "text" else f"Task: {data.task_type} ({status})"
        push.notify_threadsafe([user_id], f"Nachricht von {from_label}", label or "", "/#bus")
    return out


# ------------------------------------------------------------------ Nutzer-API
@router.post("/agents", status_code=201)
def register_agent(data: AgentCreate, request: Request, auth: Auth = Depends(get_auth),
                   conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM agents WHERE user_id = ?", (auth.id,)).fetchone()[0] >= 50:
        raise HTTPException(422, "Maximal 50 Agents pro Konto.")
    if conn.execute("SELECT 1 FROM agents WHERE user_id = ? AND name = ?", (auth.id, data.name)).fetchone():
        raise HTTPException(409, "Agent-Name bereits vergeben.")
    raw, key_hash, prefix = new_agent_key()
    cur = conn.execute(
        "INSERT INTO agents (user_id, name, description, key_hash, key_prefix, scopes, created_at) VALUES (?,?,?,?,?,?,?)",
        (auth.id, data.name, data.description, key_hash, prefix, ",".join(sorted(set(data.scopes))), now()))
    audit(conn, auth.user["username"], "agent_create", data.name, auth.id, client_ip(request))
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (cur.lastrowid,)).fetchone()
    return agent_out(row) | {"api_key": raw}  # nur hier im Klartext


@router.get("/agents")
def list_agents(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM agents WHERE user_id = ? ORDER BY id", (auth.id,))
    return {"agents": [agent_out(r) for r in rows]}


@router.post("/agents/{agent_id}/rotate")
def rotate_key(agent_id: int, request: Request, auth: Auth = Depends(get_auth),
               conn: sqlite3.Connection = Depends(get_db)):
    raw, key_hash, prefix = new_agent_key()
    cur = conn.execute("UPDATE agents SET key_hash = ?, key_prefix = ? WHERE id = ? AND user_id = ?",
                       (key_hash, prefix, agent_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Agent nicht gefunden.")
    audit(conn, auth.user["username"], "agent_rotate", str(agent_id), auth.id, client_ip(request))
    return {"api_key": raw}


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: int, request: Request, auth: Auth = Depends(get_auth),
                 conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM agents WHERE id = ? AND user_id = ?", (agent_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Agent nicht gefunden.")
    audit(conn, auth.user["username"], "agent_delete", str(agent_id), auth.id, client_ip(request))


@router.post("/messages", status_code=201)
def post_message(data: MessageSend, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return send_message(conn, auth.id, None, data)


@router.get("/messages")
def list_messages(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db),
                  agent: str | None = None, status: str | None = None,
                  before_id: int | None = None, limit: int = Query(100, ge=1, le=500)):
    q, args = "SELECT * FROM messages WHERE user_id = ?", [auth.id]
    if agent:
        q += " AND (from_label = ? OR to_label = ?)"
        args += [agent, agent]
    if status:
        q += " AND status = ?"
        args.append(status)
    if before_id:
        q += " AND id < ?"
        args.append(before_id)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return {"messages": [msg_out(r) for r in conn.execute(q, args)]}


def _set_result(conn: sqlite3.Connection, row: sqlite3.Row, body: ResultIn) -> dict:
    conn.execute("UPDATE messages SET status = ?, result = ?, updated_at = ? WHERE id = ?",
                 (body.status, json.dumps(body.result) if body.result is not None else None, now(), row["id"]))
    out = msg_out(conn.execute("SELECT * FROM messages WHERE id = ?", (row["id"],)).fetchone())
    events.publish("user", row["user_id"], "bus", out)
    sender = conn.execute("SELECT id FROM agents WHERE user_id = ? AND name = ?",
                          (row["user_id"], row["from_label"])).fetchone()
    if sender:
        events.publish("agent", sender["id"], "result", out)
    return out


@router.post("/messages/{message_id}/ack")
def ack_owner_task(message_id: int, body: ResultIn, auth: Auth = Depends(get_auth),
                   conn: sqlite3.Connection = Depends(get_db)):
    """Der Besitzer schließt eine an "todo" adressierte Task manuell ab."""
    row = conn.execute("SELECT * FROM messages WHERE id = ? AND user_id = ? AND to_label = ? AND kind = 'task'",
                       (message_id, auth.id, OWNER)).fetchone()
    if row is None:
        raise HTTPException(404, "Task nicht gefunden.")
    return _set_result(conn, row, body)


@router.get("/stream")
async def ui_stream(request: Request, auth: Auth = Depends(get_auth)):
    return await sse("user", auth.id, request)


# ------------------------------------------------------------------ Agent-API
@router.get("/inbox")
def inbox(agent: sqlite3.Row = Depends(get_agent), conn: sqlite3.Connection = Depends(get_db),
          after_id: int = 0, status: str | None = None, limit: int = Query(100, ge=1, le=500)):
    q = "SELECT * FROM messages WHERE user_id = ? AND to_label = ? AND id > ?"
    args: list = [agent["user_id"], agent["name"], after_id]
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY id LIMIT ?"
    args.append(limit)
    return {"messages": [msg_out(r) for r in conn.execute(q, args)]}


@router.post("/agent/messages", status_code=201)
def agent_send(data: MessageSend, agent: sqlite3.Row = Depends(get_agent),
               conn: sqlite3.Connection = Depends(get_db)):
    return send_message(conn, agent["user_id"], agent, data)


@router.post("/messages/{message_id}/result")
def submit_result(message_id: int, body: ResultIn, agent: sqlite3.Row = Depends(get_agent),
                  conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM messages WHERE id = ? AND user_id = ? AND to_label = ?",
                       (message_id, agent["user_id"], agent["name"])).fetchone()
    if row is None:
        raise HTTPException(404, "Nachricht nicht gefunden.")
    if row["kind"] != "task":
        raise HTTPException(422, "Nur Tasks haben ein Ergebnis.")
    return _set_result(conn, row, body)


async def sse(channel: str, key: int, request: Request):
    q = events.subscribe(channel, key)

    async def gen():
        try:
            yield "retry: 3000\n: connected\n\n"
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(q.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            events.unsubscribe(channel, key, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/inbox/stream")
async def inbox_stream(request: Request, agent: sqlite3.Row = Depends(get_agent)):
    return await sse("agent", agent["id"], request)
