"""Todo-Logik + Router (auch vom Agent Bus genutzt)."""
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AfterValidator, BaseModel, Field

from . import events
from .db import get_db, now
from .security import Auth, get_auth

router = APIRouter(prefix="/api", tags=["todos"])


def _iso_utc(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Ungültiges Datum (ISO 8601 erwartet).") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


IsoDate = Annotated[str | None, AfterValidator(_iso_utc)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    notes: str = Field(default="", max_length=5000)
    priority: int = Field(default=0, ge=0, le=3)
    due_at: IsoDate = None
    list_id: int | None = None
    parent_id: int | None = None


class TodoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)
    priority: int | None = Field(default=None, ge=0, le=3)
    due_at: IsoDate = None
    list_id: int | None = None
    done: bool | None = None


class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: Color = "#7c5cff"


class ListPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: Color | None = None


def todo_out(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["done"] = bool(d["done"])
    d.pop("reminded", None)
    d.pop("user_id", None)
    return d


def _check_list(conn: sqlite3.Connection, user_id: int, list_id: int | None) -> None:
    if list_id is not None and not conn.execute(
        "SELECT 1 FROM lists WHERE id = ? AND user_id = ?", (list_id, user_id)
    ).fetchone():
        raise HTTPException(404, "Liste nicht gefunden.")


def create_todo(conn: sqlite3.Connection, user_id: int, data: TodoIn, created_by: str = "user") -> dict:
    _check_list(conn, user_id, data.list_id)
    if data.parent_id is not None:
        parent = conn.execute(
            "SELECT parent_id FROM todos WHERE id = ? AND user_id = ?", (data.parent_id, user_id)
        ).fetchone()
        if parent is None:
            raise HTTPException(404, "Übergeordnete Aufgabe nicht gefunden.")
        if parent["parent_id"] is not None:
            raise HTTPException(422, "Nur eine Ebene Unteraufgaben erlaubt.")
    ts = now()
    cur = conn.execute(
        "INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, due_at, created_by, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, data.list_id, data.parent_id, data.title.strip(), data.notes, data.priority, data.due_at,
         created_by, ts, ts),
    )
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
    out = todo_out(row)
    events.publish("user", user_id, "todo", {"op": "created", "todo": out})
    return out


def update_todo(conn: sqlite3.Connection, user_id: int, todo_id: int, patch: dict) -> dict:
    row = conn.execute("SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    if "list_id" in patch:
        _check_list(conn, user_id, patch["list_id"])
    sets, vals = [], []
    for key in ("title", "notes", "priority", "due_at", "list_id"):
        if key in patch:
            sets.append(f"{key} = ?")
            vals.append(patch[key].strip() if key == "title" else patch[key])
    if "due_at" in patch:
        sets.append("reminded = 0")
    if "done" in patch and patch["done"] is not None:
        sets += ["done = ?", "done_at = ?"]
        vals += [int(patch["done"]), now() if patch["done"] else None]
    sets.append("updated_at = ?")
    vals.append(now())
    conn.execute(f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", (*vals, todo_id))
    out = todo_out(conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone())
    events.publish("user", user_id, "todo", {"op": "updated", "todo": out})
    return out


def list_todos(conn: sqlite3.Connection, user_id: int, done: bool | None = None, list_id: int | None = None,
               limit: int = 500) -> list[dict]:
    q, args = "SELECT * FROM todos WHERE user_id = ?", [user_id]
    if done is not None:
        q += " AND done = ?"
        args.append(int(done))
    if list_id is not None:
        q += " AND list_id = ?"
        args.append(list_id)
    q += " ORDER BY done, COALESCE(due_at, '9999'), priority DESC, id LIMIT ?"
    args.append(limit)
    return [todo_out(r) for r in conn.execute(q, args)]


# ------------------------------------------------------------------ Endpunkte
@router.get("/todos")
def api_list_todos(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db),
                   done: bool | None = None, list_id: int | None = None,
                   limit: int = Query(500, ge=1, le=2000)):
    return {"todos": list_todos(conn, auth.id, done, list_id, limit)}


@router.post("/todos", status_code=201)
def api_create_todo(data: TodoIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return create_todo(conn, auth.id, data)


@router.patch("/todos/{todo_id}")
def api_update_todo(todo_id: int, data: TodoPatch, auth: Auth = Depends(get_auth),
                    conn: sqlite3.Connection = Depends(get_db)):
    return update_todo(conn, auth.id, todo_id, data.model_dump(exclude_unset=True))


@router.delete("/todos/{todo_id}", status_code=204)
def api_delete_todo(todo_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    events.publish("user", auth.id, "todo", {"op": "deleted", "id": todo_id})


@router.post("/todos/clear-done", status_code=204)
def api_clear_done(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM todos WHERE user_id = ? AND done = 1 AND parent_id IS NULL", (auth.id,))
    events.publish("user", auth.id, "todo", {"op": "reload"})


@router.get("/lists")
def api_lists(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, name, color, created_at FROM lists WHERE user_id = ? ORDER BY id", (auth.id,))
    return {"lists": [dict(r) for r in rows]}


@router.post("/lists", status_code=201)
def api_create_list(data: ListIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("INSERT INTO lists (user_id, name, color, created_at) VALUES (?,?,?,?)",
                       (auth.id, data.name.strip(), data.color, now()))
    return {"id": cur.lastrowid, "name": data.name.strip(), "color": data.color}


@router.patch("/lists/{list_id}")
def api_patch_list(list_id: int, data: ListPatch, auth: Auth = Depends(get_auth),
                   conn: sqlite3.Connection = Depends(get_db)):
    patch = data.model_dump(exclude_none=True)
    _check_list(conn, auth.id, list_id)
    if patch:
        sets = ", ".join(f"{k} = ?" for k in patch)
        conn.execute(f"UPDATE lists SET {sets} WHERE id = ?", (*patch.values(), list_id))
    return dict(conn.execute("SELECT id, name, color FROM lists WHERE id = ?", (list_id,)).fetchone())


@router.delete("/lists/{list_id}", status_code=204)
def api_delete_list(list_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM lists WHERE id = ? AND user_id = ?", (list_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Liste nicht gefunden.")


