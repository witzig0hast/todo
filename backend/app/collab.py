"""Zusammenarbeit an Aufgaben: Abhängigkeiten („wartet auf“), Kommentare mit @Erwähnungen, Änderungsverlauf, Personen."""
import json
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import events, push
from .db import get_db, now
from .security import Auth, get_auth
from .todos import _publish, audience, enrich, get_todo, members_of, record, todo_out

router = APIRouter(prefix="/api", tags=["collab"])
MAX_DEPS = 20
MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9_.-]{3,32})")


def _refresh(conn: sqlite3.Connection, todo_id: int) -> dict:
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    out = enrich(conn, [todo_out(row)])[0]
    _publish(conn, row, {"op": "updated", "todo": out})
    return out


# ------------------------------------------------------------------ Abhängigkeiten
class DepIn(BaseModel):
    blocked_by: int


def _reaches(conn: sqlite3.Connection, start: int, target: int) -> bool:
    """Wartet `start` (transitiv) auf `target`?"""
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        if cur == target:
            return True
        if cur in seen or len(seen) > 2000:
            continue
        seen.add(cur)
        stack.extend(r["blocked_by_id"] for r in conn.execute("SELECT blocked_by_id FROM todo_deps WHERE todo_id = ?", (cur,)))
    return False


@router.post("/todos/{todo_id}/deps", status_code=201)
def add_dep(todo_id: int, data: DepIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    blocker = get_todo(conn, auth.id, data.blocked_by)
    if data.blocked_by == todo_id:
        raise HTTPException(422, "Eine Aufgabe kann nicht auf sich selbst warten.")
    if _reaches(conn, data.blocked_by, todo_id):
        raise HTTPException(422, "Das ergäbe einen Kreis: diese Aufgabe wartet schon (indirekt) auf die andere.")
    if conn.execute("SELECT COUNT(*) FROM todo_deps WHERE todo_id = ?", (todo_id,)).fetchone()[0] >= MAX_DEPS:
        raise HTTPException(422, f"Maximal {MAX_DEPS} Abhängigkeiten.")
    if conn.execute("INSERT OR IGNORE INTO todo_deps (todo_id, blocked_by_id) VALUES (?,?)", (todo_id, data.blocked_by)).rowcount:
        record(conn, todo_id, auth.user["username"], "dep_added", {"title": blocker["title"]})
    return _refresh(conn, todo_id)


@router.delete("/todos/{todo_id}/deps/{blocked_by}")
def remove_dep(todo_id: int, blocked_by: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    if conn.execute("DELETE FROM todo_deps WHERE todo_id = ? AND blocked_by_id = ?", (todo_id, blocked_by)).rowcount == 0:
        raise HTTPException(404, "Abhängigkeit nicht gefunden.")
    other = conn.execute("SELECT title FROM todos WHERE id = ?", (blocked_by,)).fetchone()
    record(conn, todo_id, auth.user["username"], "dep_removed", {"title": other["title"] if other else "?"})
    return _refresh(conn, todo_id)


# ------------------------------------------------------------------ Kommentare
class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _comment_out(r: sqlite3.Row, me: int) -> dict:
    return {"id": r["id"], "author": r["author"], "body": r["body"], "created_at": r["created_at"], "mine": r["user_id"] == me}


@router.get("/todos/{todo_id}/comments")
def list_comments(todo_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    rows = conn.execute("SELECT * FROM comments WHERE todo_id = ? ORDER BY id LIMIT 500", (todo_id,))
    return {"comments": [_comment_out(r, auth.id) for r in rows]}


@router.post("/todos/{todo_id}/comments", status_code=201)
def add_comment(todo_id: int, data: CommentIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    todo = get_todo(conn, auth.id, todo_id)
    body = data.body.strip()
    if not body:
        raise HTTPException(422, "Kommentar ist leer.")
    me = auth.user["username"]
    cur = conn.execute("INSERT INTO comments (todo_id, user_id, author, body, created_at) VALUES (?,?,?,?,?)",
                       (todo_id, auth.id, me, body, now()))
    # Erwähnt werden können nur Personen, die die Aufgabe ohnehin sehen dürfen
    people = members_of(conn, todo)
    mentioned = {people[m.lower()] for m in MENTION.findall(body) if m.lower() in people} - {auth.id}
    if mentioned:
        push.notify_threadsafe(sorted(mentioned), f"{me} hat dich erwähnt", f"{todo['title']}: {body}", "/#/all")
    others = {todo["user_id"], todo["assignee_id"]} - mentioned - {auth.id, None}
    if others and len(audience(conn, todo)) > 1:
        push.notify_threadsafe(sorted(others), f"Kommentar von {me}", f"{todo['title']}: {body}", "/#/all")
    _refresh(conn, todo_id)
    for uid in audience(conn, todo):
        events.publish("user", uid, "todo", {"op": "comment", "todo_id": todo_id})
    return _comment_out(conn.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone(), auth.id)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM comments WHERE id = ? AND user_id = ?", (comment_id, auth.id)).fetchone()
    if row is None:
        raise HTTPException(404, "Kommentar nicht gefunden (oder nicht deiner).")
    get_todo(conn, auth.id, row["todo_id"])
    conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    _refresh(conn, row["todo_id"])


# ------------------------------------------------------------------ Verlauf & Personen
@router.get("/todos/{todo_id}/history")
def history(todo_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    rows = conn.execute("SELECT * FROM todo_history WHERE todo_id = ? ORDER BY id DESC LIMIT 200", (todo_id,))
    return {"history": [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                         "detail": json.loads(r["detail"]) if r["detail"] else None} for r in rows]}


@router.get("/people")
def people(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Du selbst und alle, mit denen du Listen teilst (für Zuweisen, @Erwähnungen, Anzeige)."""
    rows = conn.execute(
        "SELECT DISTINCT u.id, u.username FROM users u WHERE u.id = :u OR u.id IN ("
        " SELECT l.user_id FROM lists l JOIN list_members m ON m.list_id = l.id WHERE m.user_id = :u"
        " UNION SELECT m2.user_id FROM list_members m2 WHERE m2.list_id IN"
        "  (SELECT id FROM lists WHERE user_id = :u UNION SELECT list_id FROM list_members WHERE user_id = :u))"
        " ORDER BY u.username COLLATE NOCASE", {"u": auth.id})
    return {"people": [{"id": r["id"], "username": r["username"]} for r in rows]}
