"""Import aus anderen Apps: Todoist (CSV-Export eines Projekts), Google Tasks (Takeout „Tasks.json“), beliebige CSV
(Microsoft To Do/Outlook-Export, Excel, eigene Tabellen) und der eigene JSON-Export dieser App.
Listen werden anhand des Namens wiederverwendet oder angelegt; Unteraufgaben bleiben erhalten (eine Ebene)."""
import csv
import io
import json
import re
import sqlite3
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import events
from .db import get_db, now, tx
from .recurrence import FMT, user_tz
from .security import Auth, enforce_rate, get_auth
from .todos import MAX_TAGS, TodoIn, can_use_list, create_todo, normalize_tags

router = APIRouter(prefix="/api", tags=["import"])
MAX_BYTES = 10 * 1024 * 1024
MAX_ITEMS = 5000

# Spaltennamen (klein) -> Feld; deckt Deutsch/Englisch, Outlook/Microsoft-To-Do-Exporte und den eigenen CSV-Export ab
ALIASES = {
    "title": ("title", "titel", "task", "aufgabe", "subject", "betreff", "name", "content", "todo"),
    "notes": ("notes", "notizen", "note", "description", "beschreibung", "body", "text", "details", "notiz"),
    "due": ("due", "due date", "due_at", "fällig", "faellig", "fällig (utc)", "fälligkeit", "datum", "date", "deadline", "fälligkeitsdatum"),
    "priority": ("priority", "priorität", "prioritaet", "importance", "wichtigkeit"),
    "tags": ("tags", "labels", "categories", "kategorien", "tag", "label"),
    "list": ("list", "liste", "project", "projekt", "folder", "ordner", "list name"),
    "done": ("done", "erledigt", "completed", "complete", "status", "abgeschlossen", "date completed"),
    "id": ("id",),
    "parent": ("parent", "übergeordnet", "parent id", "parent_id"),
}


class Importer:
    def __init__(self, conn: sqlite3.Connection, user_id: int):
        self.conn, self.user_id = conn, user_id
        self.tz = user_tz(conn, user_id)
        self.lists = {r["name"].strip().lower(): r["id"] for r in conn.execute(
            "SELECT id, name FROM lists WHERE user_id = :u OR id IN (SELECT list_id FROM list_members WHERE user_id = :u)", {"u": user_id})}
        self.new_lists: list[str] = []
        self.created: list[int] = []
        self.subtasks = 0
        self.skipped = 0

    # ---------------------------------------------------------------- Hilfen
    def list_id(self, name: str | None) -> int | None:
        name = (name or "").strip()[:60]
        if not name:
            return None
        key = name.lower()
        if key not in self.lists:
            cur = self.conn.execute("INSERT INTO lists (user_id, name, color, created_at) VALUES (?,?,?,?)",
                                    (self.user_id, name, "#8b6bff", now()))
            self.lists[key] = cur.lastrowid
            self.new_lists.append(name)
        lid = self.lists[key]
        return lid if can_use_list(self.conn, self.user_id, lid) else None

    def due(self, value: object) -> str | None:
        s = str(value or "").strip()
        if not s:
            return None
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                d = date.fromisoformat(s)
                return datetime.combine(d, time(9, 0), self.tz).astimezone(timezone.utc).strftime(FMT)
            if re.match(r"\d{4}-\d{2}-\d{2}[T ]", s):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00").replace(".000", ""))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=self.tz)
                if dt.astimezone(timezone.utc).time() == time(0, 0) and s.endswith(("Z", "00:00")):
                    # Google Tasks speichert nur das Datum (Mitternacht UTC) -> 9 Uhr Ortszeit an diesem Tag
                    dt = datetime.combine(dt.date(), time(9, 0), self.tz)
                return dt.astimezone(timezone.utc).strftime(FMT)
            m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:,?\s+(\d{1,2}):(\d{2}))?", s)
            if m:
                y = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
                return datetime(y, int(m.group(2)), int(m.group(1)), int(m.group(4) or 9), int(m.group(5) or 0),
                                tzinfo=self.tz).astimezone(timezone.utc).strftime(FMT)
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})\s*([AP]M)?)?", s, re.IGNORECASE)
            if m:  # US-Format (Outlook)
                hour, ampm = int(m.group(4) or 9), (m.group(6) or "").upper()
                if ampm:
                    hour = hour % 12 + (12 if ampm == "PM" else 0)
                return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), hour, int(m.group(5) or 0),
                                tzinfo=self.tz).astimezone(timezone.utc).strftime(FMT)
        except ValueError:
            return None
        return None

    @staticmethod
    def priority(value: object) -> int:
        s = str(value or "").strip().lower()
        if s in ("hoch", "high", "wichtig", "urgent", "dringend", "3"):
            return 3
        if s in ("mittel", "medium", "2"):
            return 2
        if s in ("niedrig", "low", "1"):
            return 1
        return 0

    @staticmethod
    def tags(value: object) -> list[str]:
        out = []
        for part in re.split(r"[,;\s]+", str(value or "")):
            try:
                out += normalize_tags([part.replace("@", "")])
            except ValueError:
                continue
        return list(dict.fromkeys(out))[:MAX_TAGS]

    @staticmethod
    def is_done(value: object) -> bool:
        s = str(value or "").strip().lower()
        return s in ("1", "true", "ja", "yes", "x", "erledigt", "completed", "done", "abgeschlossen") or bool(re.match(r"\d", s) and len(s) > 4)

    def add(self, title: str, *, notes: str = "", due: str | None = None, priority: int = 0, tags: list[str] | None = None,
            list_id: int | None = None, parent_id: int | None = None, done: bool = False) -> int | None:
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:300]
        if not title:
            self.skipped += 1
            return None
        if len(self.created) + self.subtasks >= MAX_ITEMS:
            raise HTTPException(413, f"Höchstens {MAX_ITEMS} Aufgaben pro Import.")
        t = create_todo(self.conn, self.user_id, TodoIn(title=title, notes=str(notes or "")[:5000], due_at=due if not parent_id else None,
                                                        priority=priority, tags=tags or [], list_id=list_id, parent_id=parent_id),
                        created_by="user", publish=False, done=done)
        if parent_id:
            self.subtasks += 1
        else:
            self.created.append(t["id"])
        return t["id"]

    # ---------------------------------------------------------------- Formate
    def todoist(self, text: str, list_name: str | None) -> None:
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "CONTENT" not in rows[0]:
            raise HTTPException(422, "Das ist kein Todoist-CSV (Spalte CONTENT fehlt).")
        lid = self.list_id(list_name)
        section, last_top = None, None
        for r in rows:
            kind = (r.get("TYPE") or "").strip().lower()
            content = (r.get("CONTENT") or "").strip()
            if kind == "section":
                section = content
                continue
            if kind != "task":
                continue
            labels = re.findall(r"(?<!\S)@([\w\-äöüß]+)", content)
            title = re.sub(r"(?<!\S)@[\w\-äöüß]+", "", content).strip()
            prio = {"1": 3, "2": 2, "3": 1}.get((r.get("PRIORITY") or "").strip(), 0)  # Todoist: 1 = höchste
            raw_date = (r.get("DATE") or "").strip()
            due = self.due(raw_date)
            notes = (r.get("DESCRIPTION") or "").strip()
            if raw_date and not due:
                notes = (notes + "\n" if notes else "") + f"Todoist-Datum: {raw_date}"
            tags = self.tags(" ".join(labels + ([section] if section else [])))
            indent = int((r.get("INDENT") or "1").strip() or 1)
            if indent > 1 and last_top:
                self.add(title, notes=notes, parent_id=last_top, list_id=lid)
            else:
                last_top = self.add(title, notes=notes, due=due, priority=prio, tags=tags, list_id=lid)

    def google(self, data: object) -> None:
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise HTTPException(422, "Das ist keine Google-Tasks-Datei (Tasks.json aus Google Takeout).")
        for tl in data["items"]:
            lid = self.list_id(tl.get("title"))
            items = [t for t in tl.get("items") or [] if isinstance(t, dict) and not t.get("deleted")]
            ids: dict[str, int] = {}
            for t in sorted(items, key=lambda x: bool(x.get("parent"))):  # Eltern zuerst
                parent = ids.get(t.get("parent") or "")
                new = self.add(t.get("title") or "", notes=t.get("notes") or "", due=self.due(t.get("due")), list_id=lid,
                               parent_id=parent, done=t.get("status") == "completed")
                if new and t.get("id"):
                    ids[t["id"]] = new

    def generic_csv(self, text: str) -> None:
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        header = [h.strip().lower().lstrip("﻿") for h in next(reader, [])]
        cols = {field: next((i for i, h in enumerate(header) if h in names), None) for field, names in ALIASES.items()}
        if cols["title"] is None:
            raise HTTPException(422, "Keine Titel-Spalte gefunden (z. B. „Titel“, „Title“, „Subject“, „Aufgabe“).")
        cell = lambda row, f: row[cols[f]].strip() if cols[f] is not None and cols[f] < len(row) else ""  # noqa: E731
        old_ids: dict[str, int] = {}
        pending_children = []
        for row in reader:
            if not any(c.strip() for c in row):
                continue
            title = cell(row, "title").lstrip("'")
            if cell(row, "parent"):
                pending_children.append((cell(row, "parent"), title, cell(row, "notes"), cell(row, "done")))
                continue
            new = self.add(title, notes=cell(row, "notes").lstrip("'"), due=self.due(cell(row, "due")), priority=self.priority(cell(row, "priority")),
                           tags=self.tags(cell(row, "tags")), list_id=self.list_id(cell(row, "list")), done=self.is_done(cell(row, "done")))
            if new and cell(row, "id"):
                old_ids[cell(row, "id")] = new
        for parent, title, notes, done in pending_children:
            self.add(title, notes=notes, parent_id=old_ids.get(parent), done=self.is_done(done)) if old_ids.get(parent) else self.add(title, notes=notes)

    def own_json(self, data: dict) -> None:
        names = {l["id"]: l["name"] for l in data.get("lists") or [] if isinstance(l, dict)}
        todos = [t for t in data.get("todos") or [] if isinstance(t, dict)]
        ids: dict[int, int] = {}
        for t in sorted(todos, key=lambda x: x.get("parent_id") is not None):
            parent = ids.get(t.get("parent_id")) if t.get("parent_id") else None
            if t.get("parent_id") and not parent:
                continue
            new = self.add(t.get("title") or "", notes=t.get("notes") or "", due=t.get("due_at"), priority=int(t.get("priority") or 0),
                           tags=self.tags(" ".join(t.get("tags") or [])), list_id=self.list_id(names.get(t.get("list_id"))),
                           parent_id=parent, done=bool(t.get("done")))
            if new:
                ids[t["id"]] = new


@router.post("/import")
async def import_data(request: Request, format: Literal["auto", "todoist", "google", "csv", "todo"] = "auto",
                      list_name: str | None = Query(None, max_length=60), auth: Auth = Depends(get_auth),
                      conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"import:{auth.id}", 10, 600)
    raw = await request.body()
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(413, "Datei fehlt oder ist größer als 10 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")  # Excel/Outlook unter Windows
    data = None
    if text.lstrip().startswith(("{", "[")):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise HTTPException(422, "Die Datei ist kein gültiges JSON.") from exc
    if format == "auto":
        if isinstance(data, dict) and data.get("format", "").startswith("todo-export"):
            format = "todo"
        elif isinstance(data, dict) and data.get("kind") == "tasks#taskLists":
            format = "google"
        elif data is not None:
            raise HTTPException(422, "Unbekanntes JSON-Format.")
        elif text.startswith("TYPE,CONTENT"):
            format = "todoist"
        else:
            format = "csv"
    imp = Importer(conn, auth.id)
    with tx(conn):
        if format == "todoist":
            imp.todoist(text, list_name)
        elif format == "google":
            imp.google(data)
        elif format == "todo":
            if not isinstance(data, dict):
                raise HTTPException(422, "Das ist kein Todo-Export.")
            imp.own_json(data)
        else:
            imp.generic_csv(text)
    events.publish("user", auth.id, "todo", {"op": "reload"})
    return {"format": format, "created": len(imp.created), "subtasks": imp.subtasks, "skipped": imp.skipped,
            "lists_created": imp.new_lists, "ids": imp.created}
