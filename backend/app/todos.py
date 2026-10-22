"""Todo-Logik + Router (auch vom Agent Bus genutzt): Aufgaben, Listen, Tags, Wiederholung, Erinnerungen, Filter."""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AfterValidator, BaseModel, Field, field_validator

from . import events
from .db import get_db, now
from .recurrence import FMT, Recurrence, describe, next_due, parse_utc, user_tz
from .security import Auth, get_auth

router = APIRouter(prefix="/api", tags=["todos"])

MAX_TAGS = 10
_TAG = re.compile(r"^[\w\-äöüß]{1,30}$", re.UNICODE)


def _iso_utc(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Ungültiges Datum (ISO 8601 erwartet).") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(FMT)


def normalize_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        t = str(t).strip().lstrip("#").lower()
        if not t:
            continue
        if not _TAG.match(t):
            raise ValueError(f"Ungültiger Tag '{t}' (Buchstaben, Ziffern, _ und -, max. 30 Zeichen).")
        if t not in out:
            out.append(t)
    if len(out) > MAX_TAGS:
        raise ValueError(f"Maximal {MAX_TAGS} Tags.")
    return out


def _offsets(v: list[int] | None) -> list[int] | None:
    if v is None:
        return None
    clean = sorted({int(x) for x in v})
    if len(clean) > 5 or any(x < 0 or x > 43200 for x in clean):
        raise ValueError("Bis zu 5 Erinnerungen, jeweils 0 bis 30 Tage vor Fälligkeit.")
    return clean


IsoDate = Annotated[str | None, AfterValidator(_iso_utc)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Tags = Annotated[list[str] | None, AfterValidator(lambda v: normalize_tags(v) if v is not None else None)]
Offsets = Annotated[list[int] | None, AfterValidator(_offsets)]


class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    notes: str = Field(default="", max_length=5000)
    priority: int = Field(default=0, ge=0, le=3)
    due_at: IsoDate = None
    list_id: int | None = None
    parent_id: int | None = None
    tags: Tags = None
    recurrence: Recurrence | None = None
    remind_offsets: Offsets = None


class TodoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)
    priority: int | None = Field(default=None, ge=0, le=3)
    due_at: IsoDate = None
    list_id: int | None = None
    done: bool | None = None
    tags: Tags = None
    recurrence: Recurrence | None = None
    remind_offsets: Offsets = None


class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: Color = "#7c5cff"


class ListPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: Color | None = None


class SnoozeIn(BaseModel):
    minutes: int = Field(ge=1, le=7 * 1440)


class FilterQuery(BaseModel):
    q: str = Field(default="", max_length=100)
    tags: list[str] = Field(default_factory=list)
    list_id: int | None = None
    priority_min: int = Field(default=0, ge=0, le=3)
    due: Literal["any", "overdue", "today", "week", "none"] = "any"
    include_done: bool = False

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)


class FilterIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    query: FilterQuery


def _tags_db(tags: list[str]) -> str:
    return "," + ",".join(tags) + "," if tags else ""


def todo_out(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["done"] = bool(d["done"])
    d["tags"] = [t for t in (d.get("tags") or "").split(",") if t]
    rec = json.loads(d["recurrence"]) if d.get("recurrence") else None
    d["recurrence"] = rec
    d["recurrence_text"] = describe(Recurrence(**rec)) if rec else None
    d["remind_offsets"] = json.loads(d.get("remind_offsets") or "[0]")
    d.pop("reminded", None)
    d.pop("user_id", None)
    return d


def _check_list(conn: sqlite3.Connection, user_id: int, list_id: int | None) -> None:
    if list_id is not None and not conn.execute(
        "SELECT 1 FROM lists WHERE id = ? AND user_id = ?", (list_id, user_id)
    ).fetchone():
        raise HTTPException(404, "Liste nicht gefunden.")


# ------------------------------------------------------------------ Erinnerungen
def sync_reminders(conn: sqlite3.Connection, todo_id: int) -> None:
    """Fälligkeits-Erinnerungen neu aufbauen (geschlummerte bleiben, solange die Aufgabe offen ist)."""
    t = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.execute("DELETE FROM reminders WHERE todo_id = ? AND sent = 0 AND offset_min IS NOT NULL", (todo_id,))
    if t is None or t["done"]:
        conn.execute("DELETE FROM reminders WHERE todo_id = ? AND sent = 0", (todo_id,))
        return
    if not t["due_at"]:
        return
    due = parse_utc(t["due_at"])
    current = datetime.now(timezone.utc)
    for off in json.loads(t["remind_offsets"] or "[0]"):
        at = due - timedelta(minutes=off)
        if off == 0 or at > current:  # vergangene Vorab-Erinnerungen nicht nachholen
            conn.execute("INSERT INTO reminders (todo_id, user_id, remind_at, offset_min) VALUES (?,?,?,?)",
                         (todo_id, t["user_id"], at.strftime(FMT), off))


def snooze(conn: sqlite3.Connection, user_id: int, todo_id: int, minutes: int) -> dict:
    row = conn.execute("SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime(FMT)
    conn.execute("DELETE FROM reminders WHERE todo_id = ? AND sent = 0 AND offset_min IS NULL", (todo_id,))
    conn.execute("INSERT INTO reminders (todo_id, user_id, remind_at, offset_min) VALUES (?,?,?,NULL)",
                 (todo_id, user_id, at))
    out = todo_out(row)
    out["snoozed_until"] = at
    return out


# ------------------------------------------------------------------ Aufgaben
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
        "INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, due_at, created_by, created_at, updated_at,"
        " tags, recurrence, remind_offsets) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, data.list_id, data.parent_id, data.title.strip(), data.notes, data.priority, data.due_at,
         created_by, ts, ts, _tags_db(data.tags or []),
         data.recurrence.model_dump_json() if data.recurrence else None,
         json.dumps(data.remind_offsets if data.remind_offsets is not None else [0])),
    )
    sync_reminders(conn, cur.lastrowid)
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
    out = todo_out(row)
    events.publish("user", user_id, "todo", {"op": "created", "todo": out})
    return out


def _spawn_next(conn: sqlite3.Connection, row: sqlite3.Row) -> dict | None:
    """Wiederkehrende Aufgabe erledigt -> nächste Instanz (inkl. Unteraufgaben, offen) anlegen."""
    if not row["recurrence"] or row["parent_id"] is not None:
        return None
    rec = Recurrence(**json.loads(row["recurrence"]))
    due = next_due(rec, row["due_at"], now(), user_tz(conn, row["user_id"]))
    ts = now()
    cur = conn.execute(
        "INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, due_at, created_by, created_at, updated_at,"
        " tags, recurrence, remind_offsets) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?)",
        (row["user_id"], row["list_id"], row["title"], row["notes"], row["priority"], due, row["created_by"], ts, ts,
         row["tags"], row["recurrence"], row["remind_offsets"]))
    new_id = cur.lastrowid
    for s in conn.execute("SELECT * FROM todos WHERE parent_id = ? ORDER BY id", (row["id"],)).fetchall():
        conn.execute("INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, created_by, created_at, updated_at)"
                     " VALUES (?,?,?,?,?,?,?,?,?)",
                     (s["user_id"], s["list_id"], new_id, s["title"], s["notes"], s["priority"], s["created_by"], ts, ts))
    sync_reminders(conn, new_id)
    out = todo_out(conn.execute("SELECT * FROM todos WHERE id = ?", (new_id,)).fetchone())
    events.publish("user", row["user_id"], "todo", {"op": "reload"})  # inkl. Unteraufgaben
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
    if "tags" in patch:
        sets.append("tags = ?")
        vals.append(_tags_db(patch["tags"] or []))
    if "recurrence" in patch:
        sets.append("recurrence = ?")
        rec = patch["recurrence"]
        vals.append(json.dumps(rec if isinstance(rec, dict) else rec.model_dump()) if rec else None)
    if "remind_offsets" in patch:
        sets.append("remind_offsets = ?")
        vals.append(json.dumps(patch["remind_offsets"] if patch["remind_offsets"] is not None else [0]))
    completing = patch.get("done") is True and not row["done"]
    if "done" in patch and patch["done"] is not None:
        sets += ["done = ?", "done_at = ?"]
        vals += [int(patch["done"]), now() if patch["done"] else None]
    sets.append("updated_at = ?")
    vals.append(now())
    conn.execute(f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", (*vals, todo_id))
    if {"due_at", "remind_offsets", "done"} & set(patch):
        sync_reminders(conn, todo_id)
    updated = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    out = todo_out(updated)
    events.publish("user", user_id, "todo", {"op": "updated", "todo": out})
    if completing:
        nxt = _spawn_next(conn, updated)
        if nxt:
            out["next"] = nxt
    return out


def list_todos(conn: sqlite3.Connection, user_id: int, done: bool | None = None, list_id: int | None = None,
               limit: int = 500, q: str | None = None, tag: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM todos WHERE user_id = ?", [user_id]
    if done is not None:
        sql += " AND done = ?"
        args.append(int(done))
    if list_id is not None:
        sql += " AND list_id = ?"
        args.append(list_id)
    if q:
        sql += " AND (title LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')"
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args += [like, like, like]
    if tag:
        sql += " AND tags LIKE ?"
        args.append(f"%,{normalize_tags([tag])[0]},%")
    sql += " ORDER BY done, COALESCE(due_at, '9999'), priority DESC, id LIMIT ?"
    args.append(limit)
    return [todo_out(r) for r in conn.execute(sql, args)]


# ------------------------------------------------------------------ Endpunkte
@router.get("/todos")
def api_list_todos(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db),
                   done: bool | None = None, list_id: int | None = None, q: str | None = Query(None, max_length=100),
                   tag: str | None = Query(None, max_length=30), limit: int = Query(2000, ge=1, le=5000)):
    try:
        return {"todos": list_todos(conn, auth.id, done, list_id, limit, q, tag)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/todos", status_code=201)
def api_create_todo(data: TodoIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return create_todo(conn, auth.id, data)


@router.patch("/todos/{todo_id}")
def api_update_todo(todo_id: int, data: TodoPatch, auth: Auth = Depends(get_auth),
                    conn: sqlite3.Connection = Depends(get_db)):
    return update_todo(conn, auth.id, todo_id, data.model_dump(exclude_unset=True))


@router.post("/todos/{todo_id}/snooze")
def api_snooze(todo_id: int, data: SnoozeIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return snooze(conn, auth.id, todo_id, data.minutes)


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


@router.get("/tags")
def api_tags(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    counts: dict[str, int] = {}
    for r in conn.execute("SELECT tags FROM todos WHERE user_id = ? AND done = 0 AND tags != ''", (auth.id,)):
        for t in r["tags"].split(","):
            if t:
                counts[t] = counts.get(t, 0) + 1
    return {"tags": [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]}


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


# ------------------------------------------------------------------ Gespeicherte Filter
@router.get("/filters")
def api_filters(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, name, query FROM saved_filters WHERE user_id = ? ORDER BY id", (auth.id,))
    return {"filters": [{"id": r["id"], "name": r["name"], "query": json.loads(r["query"])} for r in rows]}


@router.post("/filters", status_code=201)
def api_create_filter(data: FilterIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM saved_filters WHERE user_id = ?", (auth.id,)).fetchone()[0] >= 30:
        raise HTTPException(422, "Maximal 30 gespeicherte Filter.")
    cur = conn.execute("INSERT INTO saved_filters (user_id, name, query, created_at) VALUES (?,?,?,?)",
                       (auth.id, data.name.strip(), data.query.model_dump_json(), now()))
    return {"id": cur.lastrowid, "name": data.name.strip(), "query": data.query.model_dump()}


@router.delete("/filters/{filter_id}", status_code=204)
def api_delete_filter(filter_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM saved_filters WHERE id = ? AND user_id = ?", (filter_id, auth.id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Filter nicht gefunden.")
