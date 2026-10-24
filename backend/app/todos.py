"""Todo-Logik + Router (auch vom Agent Bus genutzt): Aufgaben, Listen, Tags, Wiederholung, Erinnerungen, Filter."""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AfterValidator, BaseModel, Field, field_validator

from . import events
from .db import get_db, now, tx
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


class Location(BaseModel):
    name: str = Field(default="", max_length=80)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius: int = Field(default=200, ge=50, le=5000)  # Meter


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
    location: Location | None = None


class TodoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    stage: Literal["todo", "doing"] | None = None
    assignee: str | None = Field(default=None, max_length=64)  # Benutzername, "" = niemand
    notes: str | None = Field(default=None, max_length=5000)
    priority: int | None = Field(default=None, ge=0, le=3)
    due_at: IsoDate = None
    list_id: int | None = None
    done: bool | None = None
    tags: Tags = None
    recurrence: Recurrence | None = None
    remind_offsets: Offsets = None
    location: Location | None = None


class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: Color = "#7c5cff"
    kind: Literal["list", "project"] = "list"
    due_at: IsoDate = None


class ListPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: Color | None = None
    kind: Literal["list", "project"] | None = None
    due_at: IsoDate = None


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
    d["location"] = json.loads(d["location"]) if d.get("location") else None
    d.pop("reminded", None)
    d.pop("user_id", None)
    return d


# ------------------------------------------------------------------ Verlauf, Abhängigkeiten, Kommentare (Zusatzinfos)
HISTORY_FIELDS = ("title", "due_at", "done", "list_id", "priority", "assignee_id", "stage", "notes", "recurrence")


def actor_name(conn: sqlite3.Connection, user_id: int) -> str:
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["username"] if row else "?"


def record(conn: sqlite3.Connection, todo_id: int, actor: str, action: str, detail: object = None) -> None:
    conn.execute("INSERT INTO todo_history (todo_id, actor, action, detail, at) VALUES (?,?,?,?,?)",
                 (todo_id, actor[:64], action, json.dumps(detail, ensure_ascii=False) if detail is not None else None, now()))


def enrich(conn: sqlite3.Connection, items: list[dict]) -> list[dict]:
    """Ergänzt blocked_by (IDs) und comment_count für eine Liste von Aufgaben (zwei Abfragen statt N)."""
    if not items:
        return items
    ids = [t["id"] for t in items]
    marks = ",".join("?" * len(ids))
    deps: dict[int, list[int]] = {}
    for r in conn.execute(f"SELECT todo_id, blocked_by_id FROM todo_deps WHERE todo_id IN ({marks})", ids):
        deps.setdefault(r["todo_id"], []).append(r["blocked_by_id"])
    counts = {r["todo_id"]: r["n"] for r in conn.execute(
        f"SELECT todo_id, COUNT(*) AS n FROM comments WHERE todo_id IN ({marks}) GROUP BY todo_id", ids)}
    for t in items:
        t["blocked_by"] = deps.get(t["id"], [])
        t["comment_count"] = counts.get(t["id"], 0)
    return items


# ------------------------------------------------------------------ Zugriff (eigene + geteilte Listen)
ACCESS_SQL = ("(t.user_id = :u OR t.list_id IN (SELECT id FROM lists WHERE user_id = :u "
              "UNION SELECT list_id FROM list_members WHERE user_id = :u))")


def can_use_list(conn: sqlite3.Connection, user_id: int, list_id: int) -> bool:
    return conn.execute("SELECT 1 FROM lists WHERE id = :l AND (user_id = :u OR id IN "
                        "(SELECT list_id FROM list_members WHERE user_id = :u))", {"l": list_id, "u": user_id}).fetchone() is not None


def _check_list(conn: sqlite3.Connection, user_id: int, list_id: int | None) -> None:
    if list_id is not None and not can_use_list(conn, user_id, list_id):
        raise HTTPException(404, "Liste nicht gefunden.")


def get_todo(conn: sqlite3.Connection, user_id: int, todo_id: int) -> sqlite3.Row:
    """Aufgabe, auf die der Benutzer zugreifen darf (eigene oder in einer eigenen/geteilten Liste) - sonst 404."""
    row = conn.execute(f"SELECT t.* FROM todos t WHERE t.id = :id AND {ACCESS_SQL}", {"id": todo_id, "u": user_id}).fetchone()
    if row is None:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    return row


def audience(conn: sqlite3.Connection, todo: sqlite3.Row | dict) -> set[int]:
    """Alle Benutzer, die die Aufgabe sehen (für Live-Updates)."""
    users = {todo["user_id"]}
    if todo["list_id"]:
        lst = conn.execute("SELECT user_id FROM lists WHERE id = ?", (todo["list_id"],)).fetchone()
        if lst:
            users.add(lst["user_id"])
        users.update(r["user_id"] for r in conn.execute("SELECT user_id FROM list_members WHERE list_id = ?", (todo["list_id"],)))
    return users


def members_of(conn: sqlite3.Connection, todo: sqlite3.Row | dict) -> dict[str, int]:
    """Wer eine Aufgabe zugewiesen bekommen kann: Besitzer der Aufgabe/Liste und Listenmitglieder (freigegeben)."""
    marks = ",".join("?" * len(audience(conn, todo)))
    return {r["username"].lower(): r["id"] for r in conn.execute(
        f"SELECT id, username FROM users WHERE status = 'approved' AND id IN ({marks})", tuple(audience(conn, todo)))}


def _publish(conn: sqlite3.Connection, todo: sqlite3.Row | dict, payload: dict) -> None:
    for uid in audience(conn, todo):
        events.publish("user", uid, "todo", payload)


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
    row = get_todo(conn, user_id, todo_id)
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
        try:
            parent = get_todo(conn, user_id, data.parent_id)
        except HTTPException as exc:
            raise HTTPException(404, "Übergeordnete Aufgabe nicht gefunden.") from exc
        if parent["parent_id"] is not None:
            raise HTTPException(422, "Nur eine Ebene Unteraufgaben erlaubt.")
    ts = now()
    cur = conn.execute(
        "INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, due_at, created_by, created_at, updated_at,"
        " tags, recurrence, remind_offsets, location) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, data.list_id, data.parent_id, data.title.strip(), data.notes, data.priority, data.due_at,
         created_by, ts, ts, _tags_db(data.tags or []),
         data.recurrence.model_dump_json() if data.recurrence else None,
         json.dumps(data.remind_offsets if data.remind_offsets is not None else [0]),
         data.location.model_dump_json() if data.location else None),
    )
    sync_reminders(conn, cur.lastrowid)
    record(conn, cur.lastrowid, created_by if created_by != "user" else actor_name(conn, user_id), "created")
    if data.location:
        _geofences_changed(conn, user_id)
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
    out = enrich(conn, [todo_out(row)])[0]
    _publish(conn, row, {"op": "created", "todo": out})
    return out


def _geofences_changed(conn: sqlite3.Connection, user_id: int) -> None:
    from .devices import notify_geofences_changed  # spät importieren

    notify_geofences_changed(conn, user_id)


def _spawn_next(conn: sqlite3.Connection, row: sqlite3.Row, publish: bool = True) -> dict | None:
    """Wiederkehrende Aufgabe erledigt -> nächste Instanz (inkl. Unteraufgaben, offen) anlegen."""
    if not row["recurrence"] or row["parent_id"] is not None:
        return None
    rec = Recurrence(**json.loads(row["recurrence"]))
    due = next_due(rec, row["due_at"], now(), user_tz(conn, row["user_id"]))
    ts = now()
    cur = conn.execute(
        "INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, due_at, created_by, created_at, updated_at,"
        " tags, recurrence, remind_offsets, location) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,?)",
        (row["user_id"], row["list_id"], row["title"], row["notes"], row["priority"], due, row["created_by"], ts, ts,
         row["tags"], row["recurrence"], row["remind_offsets"], row["location"]))
    new_id = cur.lastrowid
    for s in conn.execute("SELECT * FROM todos WHERE parent_id = ? ORDER BY id", (row["id"],)).fetchall():
        conn.execute("INSERT INTO todos (user_id, list_id, parent_id, title, notes, priority, created_by, created_at, updated_at)"
                     " VALUES (?,?,?,?,?,?,?,?,?)",
                     (s["user_id"], s["list_id"], new_id, s["title"], s["notes"], s["priority"], s["created_by"], ts, ts))
    sync_reminders(conn, new_id)
    out = todo_out(conn.execute("SELECT * FROM todos WHERE id = ?", (new_id,)).fetchone())
    if publish:
        _publish(conn, row, {"op": "reload"})  # inkl. Unteraufgaben
    return out


def _notify_unblocked(conn: sqlite3.Connection, todo_id: int, actor_id: int) -> None:
    """Aufgaben, die nur noch auf diese gewartet haben, sind jetzt frei: Zuständige(n) bzw. Besitzer benachrichtigen."""
    from . import push

    for t in conn.execute("SELECT t.* FROM todo_deps d JOIN todos t ON t.id = d.todo_id WHERE d.blocked_by_id = ? AND t.done = 0",
                          (todo_id,)).fetchall():
        still = conn.execute("SELECT 1 FROM todo_deps d JOIN todos b ON b.id = d.blocked_by_id WHERE d.todo_id = ? AND b.done = 0",
                             (t["id"],)).fetchone()
        who = t["assignee_id"] or t["user_id"]
        if still is None and who != actor_id:
            push.notify_threadsafe([who], "Kann losgehen", t["title"], "/#/all")


def update_todo(conn: sqlite3.Connection, user_id: int, todo_id: int, patch: dict, publish: bool = True,
                actor: str | None = None) -> dict:
    row = get_todo(conn, user_id, todo_id)
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
    if "location" in patch:
        sets.append("location = ?")
        loc = patch["location"]
        vals.append(json.dumps(loc if isinstance(loc, dict) else loc.model_dump()) if loc else None)
    if "remind_offsets" in patch:
        sets.append("remind_offsets = ?")
        vals.append(json.dumps(patch["remind_offsets"] if patch["remind_offsets"] is not None else [0]))
    if patch.get("stage"):
        sets.append("stage = ?")
        vals.append(patch["stage"])
        if row["done"] and "done" not in patch:  # auf dem Board aus „Erledigt“ zurückgezogen
            patch["done"] = False
    assignee_changed = False
    if "assignee" in patch:
        name = (patch["assignee"] or "").strip().lower()
        if name:
            target = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
            new_list = patch.get("list_id", row["list_id"])
            cand = members_of(conn, {**dict(target), "list_id": new_list})
            if name not in cand:
                raise HTTPException(422, "Zuweisen geht nur an dich oder Mitglieder der geteilten Liste.")
            new_assignee = cand[name]
        else:
            new_assignee = None
        assignee_changed = new_assignee != row["assignee_id"]
        sets.append("assignee_id = ?")
        vals.append(new_assignee)
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
    actor = actor or actor_name(conn, user_id)
    for f in HISTORY_FIELDS:
        if row[f] != updated[f]:
            if f == "notes":
                record(conn, todo_id, actor, "notes")
            elif f == "assignee_id":
                record(conn, todo_id, actor, "assignee", {"to": actor_name(conn, updated[f]) if updated[f] else None})
            else:
                record(conn, todo_id, actor, f, {"from": row[f], "to": updated[f]})
    if assignee_changed and updated["assignee_id"] and updated["assignee_id"] != user_id:
        from . import push

        push.notify_threadsafe([updated["assignee_id"]], "Neue Aufgabe für dich", f"{actor}: {updated['title']}", "/#/assigned")
    if completing:
        _notify_unblocked(conn, todo_id, user_id)
    if "location" in patch or (row["location"] and ("done" in patch or "title" in patch)):
        _geofences_changed(conn, user_id)
    out = enrich(conn, [todo_out(updated)])[0]
    if publish:
        _publish(conn, updated, {"op": "updated", "todo": out})
        if row["list_id"] != updated["list_id"]:
            _publish(conn, row, {"op": "reload"})  # aus geteilter Liste verschoben
    if completing:
        nxt = _spawn_next(conn, updated, publish)
        if nxt:
            out["next"] = nxt
    return out


def list_todos(conn: sqlite3.Connection, user_id: int, done: bool | None = None, list_id: int | None = None,
               limit: int = 500, q: str | None = None, tag: str | None = None) -> list[dict]:
    sql, args = f"SELECT t.* FROM todos t WHERE {ACCESS_SQL}", {"u": user_id}
    if done is not None:
        sql += " AND t.done = :done"
        args["done"] = int(done)
    if list_id is not None:
        sql += " AND t.list_id = :list"
        args["list"] = list_id
    if q:
        sql += " AND (t.title LIKE :like ESCAPE '\\' OR t.notes LIKE :like ESCAPE '\\' OR t.tags LIKE :like ESCAPE '\\')"
        args["like"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    if tag:
        sql += " AND t.tags LIKE :tag"
        args["tag"] = f"%,{normalize_tags([tag])[0]},%"
    sql += " ORDER BY t.done, COALESCE(t.due_at, '9999'), t.priority DESC, t.id LIMIT :limit"
    args["limit"] = limit
    return enrich(conn, [todo_out(r) for r in conn.execute(sql, args)])


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


@router.delete("/todos/{todo_id}")
def api_delete_todo(todo_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Verschiebt die Aufgabe (samt Unteraufgaben, Anhängen) in den Papierkorb - mit Rückgängig."""
    from . import trash

    row = get_todo(conn, auth.id, todo_id)
    return {"trash_id": trash.move(conn, auth.id, [row], row["title"])}


@router.post("/todos/clear-done")
def api_clear_done(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    from . import trash

    rows = conn.execute("SELECT * FROM todos WHERE user_id = ? AND done = 1 AND parent_id IS NULL", (auth.id,)).fetchall()
    if not rows:
        return {"trash_id": None, "count": 0}
    return {"trash_id": trash.move(conn, auth.id, rows, f"{len(rows)} erledigte Aufgabe{'n' if len(rows) != 1 else ''}"),
            "count": len(rows)}


# ------------------------------------------------------------------ Sammelaktionen (Mehrfachauswahl)
class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["done", "undone", "delete", "move", "tag", "untag", "due", "priority"]
    list_id: int | None = None
    tags: Tags = None
    due_at: IsoDate = None
    priority: int | None = Field(default=None, ge=0, le=3)


@router.post("/todos/bulk")
def api_bulk(data: BulkIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    rows = []
    for tid in dict.fromkeys(data.ids):
        try:
            rows.append(get_todo(conn, auth.id, tid))
        except HTTPException:
            continue  # nicht (mehr) zugänglich: überspringen
    if not rows:
        raise HTTPException(404, "Keine der Aufgaben gefunden.")
    if data.action == "delete":
        from . import trash

        tops = [r for r in rows if r["parent_id"] is None or r["parent_id"] not in {x["id"] for x in rows}]
        title = tops[0]["title"] if len(tops) == 1 else f"{len(tops)} Aufgaben"
        return {"count": len(tops), "trash_id": trash.move(conn, auth.id, tops, title)}
    if data.action == "move":
        _check_list(conn, auth.id, data.list_id)
    users: set[int] = set()
    with tx(conn):
        for r in rows:
            users |= audience(conn, r)
            if data.action in ("done", "undone"):
                patch = {"done": data.action == "done"}
            elif data.action == "move":
                patch = {"list_id": data.list_id}
            elif data.action in ("tag", "untag"):
                cur = [t for t in (r["tags"] or "").split(",") if t]
                new = data.tags or []
                tags = [t for t in cur if t not in new] if data.action == "untag" else list(dict.fromkeys(cur + new))
                patch = {"tags": tags[:MAX_TAGS]}
            elif data.action == "due":
                patch = {"due_at": data.due_at}
            else:
                patch = {"priority": data.priority if data.priority is not None else 0}
            updated = update_todo(conn, auth.id, r["id"], patch, publish=False)
            users |= audience(conn, conn.execute("SELECT * FROM todos WHERE id = ?", (updated["id"],)).fetchone())
    for uid in users:
        events.publish("user", uid, "todo", {"op": "reload"})
    return {"count": len(rows)}


# ------------------------------------------------------------------ Schnelleingabe (ohne KI)
class QuickIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    list_id: int | None = None
    tags: Tags = None
    raw: bool = False  # Erkennung aus: Text 1:1 als Titel


def _quick(conn: sqlite3.Connection, user_id: int, data: QuickIn) -> dict:
    from . import quickparse

    if data.raw:
        return {"title": data.text.strip(), "due_at": None, "priority": 0, "tags": [], "list_id": None,
                "recurrence": None, "recurrence_text": None}
    lists = {r["id"]: r["name"] for r in conn.execute(
        "SELECT id, name FROM lists WHERE user_id = :u OR id IN (SELECT list_id FROM list_members WHERE user_id = :u)",
        {"u": user_id})}
    return quickparse.parse(data.text, datetime.now(timezone.utc).astimezone(user_tz(conn, user_id)), lists)


@router.post("/quick/parse")
def api_quick_parse(data: QuickIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return _quick(conn, auth.id, data)


@router.post("/todos/quick", status_code=201)
def api_quick_create(data: QuickIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    p = _quick(conn, auth.id, data)
    tags = list(dict.fromkeys(p["tags"] + (data.tags or [])))[:MAX_TAGS]
    try:
        todo = TodoIn(title=p["title"][:300], due_at=p["due_at"], priority=p["priority"], tags=tags,
                      list_id=p["list_id"] if p["list_id"] is not None else data.list_id,
                      recurrence=Recurrence(**p["recurrence"]) if p["recurrence"] else None)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return create_todo(conn, auth.id, todo)


# ------------------------------------------------------------------ Zeiterfassung (Fokus-Timer)
class TimeIn(BaseModel):
    minutes: int = Field(ge=1, le=600)
    started_at: IsoDate = None


@router.post("/todos/{todo_id}/time")
def api_track_time(todo_id: int, data: TimeIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    ts = now()
    conn.execute("INSERT INTO time_entries (todo_id, user_id, started_at, minutes, created_at) VALUES (?,?,?,?,?)",
                 (todo_id, auth.id, data.started_at or ts, data.minutes, ts))
    conn.execute("UPDATE todos SET tracked_min = tracked_min + ? WHERE id = ?", (data.minutes, todo_id))
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    out = todo_out(row)
    _publish(conn, row, {"op": "updated", "todo": out})
    return out


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
    out = []
    for r in conn.execute("SELECT l.*, u.username AS owner FROM lists l JOIN users u ON u.id = l.user_id WHERE l.user_id = :u "
                          "OR l.id IN (SELECT list_id FROM list_members WHERE user_id = :u) ORDER BY l.id", {"u": auth.id}):
        members = [m["username"] for m in conn.execute("SELECT u.username FROM list_members m JOIN users u ON u.id = m.user_id "
                                                         "WHERE m.list_id = ? ORDER BY u.username", (r["id"],))]
        mine = r["user_id"] == auth.id
        out.append({"id": r["id"], "name": r["name"], "color": r["color"], "created_at": r["created_at"],
                    "owner": r["owner"], "mine": mine, "members": members, "kind": r["kind"], "due_at": r["due_at"]})
    return {"lists": out}


class MemberIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


def _own_list(conn: sqlite3.Connection, user_id: int, list_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM lists WHERE id = ? AND user_id = ?", (list_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Liste nicht gefunden (oder nicht deine).")
    return row


@router.post("/lists/{list_id}/members", status_code=201)
def api_add_member(list_id: int, data: MemberIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    _own_list(conn, auth.id, list_id)
    target = conn.execute("SELECT id, username FROM users WHERE username = ? AND status = 'approved'", (data.username.strip(),)).fetchone()
    if target is None or target["id"] == auth.id:
        raise HTTPException(404, "Benutzer nicht gefunden.")
    if conn.execute("SELECT COUNT(*) FROM list_members WHERE list_id = ?", (list_id,)).fetchone()[0] >= 20:
        raise HTTPException(422, "Maximal 20 Mitglieder pro Liste.")
    conn.execute("INSERT OR IGNORE INTO list_members (list_id, user_id, added_at) VALUES (?,?,?)", (list_id, target["id"], now()))
    events.publish("user", target["id"], "todo", {"op": "reload"})
    from . import push

    push.notify_threadsafe([target["id"]], "Liste geteilt", f"{auth.user['username']} hat eine Liste mit dir geteilt.", "/")
    return {"username": target["username"]}


@router.delete("/lists/{list_id}/members/{username}", status_code=204)
def api_remove_member(list_id: int, username: str, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Besitzer entfernt ein Mitglied - oder ein Mitglied verlässt die Liste selbst."""
    lst = conn.execute("SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()
    target = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if lst is None or target is None or not (lst["user_id"] == auth.id or target["id"] == auth.id):
        raise HTTPException(404, "Mitglied nicht gefunden.")
    if conn.execute("DELETE FROM list_members WHERE list_id = ? AND user_id = ?", (list_id, target["id"])).rowcount == 0:
        raise HTTPException(404, "Mitglied nicht gefunden.")
    for uid in (lst["user_id"], target["id"]):
        events.publish("user", uid, "todo", {"op": "reload"})


@router.post("/lists", status_code=201)
def api_create_list(data: ListIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("INSERT INTO lists (user_id, name, color, created_at, kind, due_at) VALUES (?,?,?,?,?,?)",
                       (auth.id, data.name.strip(), data.color, now(), data.kind, data.due_at))
    return {"id": cur.lastrowid, "name": data.name.strip(), "color": data.color, "kind": data.kind, "due_at": data.due_at,
            "owner": auth.user["username"], "mine": True, "members": []}


@router.patch("/lists/{list_id}")
def api_patch_list(list_id: int, data: ListPatch, auth: Auth = Depends(get_auth),
                   conn: sqlite3.Connection = Depends(get_db)):
    patch = data.model_dump(exclude_unset=True)
    for k in ("name", "color", "kind"):
        if k in patch and patch[k] is None:
            patch.pop(k)
    _own_list(conn, auth.id, list_id)
    if patch:
        sets = ", ".join(f"{k} = ?" for k in patch)
        conn.execute(f"UPDATE lists SET {sets} WHERE id = ?", (*patch.values(), list_id))
    for uid in {r["user_id"] for r in conn.execute("SELECT user_id FROM list_members WHERE list_id = ?", (list_id,))}:
        events.publish("user", uid, "todo", {"op": "reload"})
    return dict(conn.execute("SELECT id, name, color, kind, due_at FROM lists WHERE id = ?", (list_id,)).fetchone())


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
