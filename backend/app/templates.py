"""Vorlagen: wiederkehrende Checklisten („Urlaub packen“, „Server-Update“) mit Unteraufgaben und relativer Fälligkeit."""
import json
import sqlite3
from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .db import get_db, now
from .recurrence import FMT, user_tz
from .security import Auth, get_auth
from .todos import Offsets, Tags, TodoIn, can_use_list, create_todo

router = APIRouter(prefix="/api/templates", tags=["templates"])
MAX_TEMPLATES = 100

SubTitle = Annotated[str, Field(min_length=1, max_length=300)]


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=300)
    notes: str = Field(default="", max_length=5000)
    priority: int = Field(default=0, ge=0, le=3)
    tags: Tags = None
    list_id: int | None = None
    due_days: int | None = Field(default=None, ge=0, le=365)  # fällig in N Tagen (None = ohne Fälligkeit)
    due_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    remind_offsets: Offsets = None
    subtasks: list[SubTitle] = Field(default_factory=list, max_length=50)


class UseIn(BaseModel):
    list_id: int | None = None   # überschreibt die Liste der Vorlage
    title: str | None = Field(default=None, max_length=300)


def _out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "used_count": r["used_count"], **json.loads(r["data"])}


def _get(conn: sqlite3.Connection, user_id: int, tpl_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM templates WHERE id = ? AND user_id = ?", (tpl_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Vorlage nicht gefunden.")
    return row


def _check(conn: sqlite3.Connection, user_id: int, data: TemplateIn) -> str:
    if data.list_id is not None and not can_use_list(conn, user_id, data.list_id):
        raise HTTPException(404, "Liste nicht gefunden.")
    return data.model_dump_json(exclude={"name"})


@router.get("")
def list_templates(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM templates WHERE user_id = ? ORDER BY used_count DESC, name COLLATE NOCASE", (auth.id,))
    return {"templates": [_out(r) for r in rows]}


@router.post("", status_code=201)
def create_template(data: TemplateIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM templates WHERE user_id = ?", (auth.id,)).fetchone()[0] >= MAX_TEMPLATES:
        raise HTTPException(422, f"Maximal {MAX_TEMPLATES} Vorlagen.")
    cur = conn.execute("INSERT INTO templates (user_id, name, data, created_at) VALUES (?,?,?,?)",
                       (auth.id, data.name.strip(), _check(conn, auth.id, data), now()))
    return _out(_get(conn, auth.id, cur.lastrowid))


@router.put("/{tpl_id}")
def update_template(tpl_id: int, data: TemplateIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _get(conn, auth.id, tpl_id)
    conn.execute("UPDATE templates SET name = ?, data = ? WHERE id = ?", (data.name.strip(), _check(conn, auth.id, data), tpl_id))
    return _out(_get(conn, auth.id, tpl_id))


@router.delete("/{tpl_id}", status_code=204)
def delete_template(tpl_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _get(conn, auth.id, tpl_id)
    conn.execute("DELETE FROM templates WHERE id = ?", (tpl_id,))


def instantiate(conn: sqlite3.Connection, user_id: int, tpl: TemplateIn, list_id: int | None, title: str | None,
                now_utc: datetime | None = None) -> dict:
    due = None
    if tpl.due_days is not None:
        local = (now_utc or datetime.now(timezone.utc)).astimezone(user_tz(conn, user_id))
        h, m = map(int, (tpl.due_time or "09:00").split(":"))
        due = datetime.combine(local.date() + timedelta(days=tpl.due_days), time(h, m), local.tzinfo)
        due = due.astimezone(timezone.utc).strftime(FMT)
    lid = list_id if list_id is not None else tpl.list_id
    if lid is not None and not can_use_list(conn, user_id, lid):
        lid = None  # Liste der Vorlage gibt es nicht mehr
    parent = create_todo(conn, user_id, TodoIn(title=(title or tpl.title).strip() or tpl.title, notes=tpl.notes,
                                               priority=tpl.priority, due_at=due, list_id=lid, tags=tpl.tags,
                                               remind_offsets=tpl.remind_offsets))
    for s in tpl.subtasks:
        create_todo(conn, user_id, TodoIn(title=s, parent_id=parent["id"], list_id=lid))
    return parent


@router.post("/{tpl_id}/use", status_code=201)
def use_template(tpl_id: int, data: UseIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = _get(conn, auth.id, tpl_id)
    tpl = TemplateIn(name=row["name"], **json.loads(row["data"]))
    out = instantiate(conn, auth.id, tpl, data.list_id, data.title)
    conn.execute("UPDATE templates SET used_count = used_count + 1 WHERE id = ?", (tpl_id,))
    return out
