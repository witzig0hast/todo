"""Regeln für eingehende Agent-Nachrichten: "Wenn Agent X 'Fehler' meldet -> Aufgabe anlegen / Gerät benachrichtigen"."""
import json
import re
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import devices
from .db import get_db, now
from .security import Auth, get_auth, limiter

router = APIRouter(prefix="/api/rules", tags=["rules"])
MAX_RULES = 50
FIRES_PER_HOUR = 30  # Schutz gegen Fluten


class Match(BaseModel):
    agent: str = Field(default="", max_length=64)          # leer = alle Agents
    kind: Literal["any", "text", "task"] = "any"
    contains: str = Field(default="", max_length=200)      # Text in Inhalt oder Payload (ohne Groß/klein)
    task_type: str = Field(default="", max_length=64)


class Action(BaseModel):
    type: Literal["create_todo", "notify"]
    title: str = Field(default="{content}", min_length=1, max_length=300)   # Vorlage
    body: str = Field(default="", max_length=500)
    priority: int = Field(default=0, ge=0, le=3)
    tags: list[str] = Field(default_factory=list)
    device: str = Field(default="", max_length=60)          # leer = alle Geräte (nur notify)
    urgent: bool = False

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        from .todos import normalize_tags

        return normalize_tags(v)


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    match: Match
    action: Action


class RulePatch(BaseModel):
    enabled: bool | None = None


def rule_out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "enabled": bool(r["enabled"]), "match": json.loads(r["match"]),
            "action": json.loads(r["action"]), "fire_count": r["fire_count"], "last_fired_at": r["last_fired_at"]}


def _text_of(msg: dict) -> str:
    return " ".join(filter(None, [msg.get("content") or "", msg.get("task_type") or "",
                                  json.dumps(msg["payload"], ensure_ascii=False) if msg.get("payload") else ""])).lower()


def matches(match: dict, msg: dict) -> bool:
    if match.get("agent") and match["agent"].lower() != msg["from_label"].lower():
        return False
    if match.get("kind", "any") != "any" and match["kind"] != msg["kind"]:
        return False
    if match.get("task_type") and match["task_type"] != (msg.get("task_type") or ""):
        return False
    if match.get("contains") and match["contains"].lower() not in _text_of(msg):
        return False
    return True


_VAR = re.compile(r"\{(agent|content|task_type|payload\.[A-Za-z0-9_]{1,40})\}")


def render(template: str, msg: dict) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key == "agent":
            return msg["from_label"]
        if key == "content":
            return msg.get("content") or (msg.get("task_type") or "")
        if key == "task_type":
            return msg.get("task_type") or ""
        val = (msg.get("payload") or {}).get(key.split(".", 1)[1]) if isinstance(msg.get("payload"), dict) else None
        return "" if val is None else str(val)

    return _VAR.sub(sub, template).strip()


def evaluate(conn: sqlite3.Connection, user_id: int, msg: dict) -> list[str]:
    """Wendet alle passenden, aktiven Regeln an. Gibt die Namen der ausgelösten Regeln zurück."""
    from . import todos

    fired: list[str] = []
    for r in conn.execute("SELECT * FROM rules WHERE user_id = ? AND enabled = 1 ORDER BY id", (user_id,)).fetchall():
        match, action = json.loads(r["match"]), json.loads(r["action"])
        if not matches(match, msg):
            continue
        key = f"rule:{r['id']}"
        if limiter.blocked(key, FIRES_PER_HOUR, 3600):
            continue
        limiter.hit(key, 3600)
        title = (render(action["title"], msg) or r["name"])[:300]
        try:
            if action["type"] == "create_todo":
                todos.create_todo(conn, user_id, todos.TodoIn(title=title, notes=render(action.get("body", ""), msg)[:5000],
                                                              priority=action.get("priority", 0), tags=action.get("tags") or []),
                                  created_by=msg["from_label"])
            else:
                device_id = None
                if action.get("device"):
                    d = conn.execute("SELECT id FROM devices WHERE user_id = ? AND name = ? COLLATE NOCASE",
                                     (user_id, action["device"])).fetchone()
                    if d is None:
                        continue
                    device_id = d["id"]
                devices.enqueue(conn, user_id, title[:80], render(action.get("body", ""), msg)[:500], "/#/bus", device_id,
                                urgent=bool(action.get("urgent")), bus_message_id=msg["id"])
        except (ValueError, LookupError, HTTPException):
            continue
        conn.execute("UPDATE rules SET fire_count = fire_count + 1, last_fired_at = ? WHERE id = ?", (now(), r["id"]))
        fired.append(r["name"])
    return fired


# ------------------------------------------------------------------ API
@router.get("")
def list_rules(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    return {"rules": [rule_out(r) for r in conn.execute("SELECT * FROM rules WHERE user_id = ? ORDER BY id", (auth.id,))]}


@router.post("", status_code=201)
def create_rule(data: RuleIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM rules WHERE user_id = ?", (auth.id,)).fetchone()[0] >= MAX_RULES:
        raise HTTPException(422, f"Maximal {MAX_RULES} Regeln.")
    if not (data.match.agent or data.match.contains or data.match.task_type or data.match.kind != "any"):
        raise HTTPException(422, "Bitte mindestens eine Bedingung angeben.")
    cur = conn.execute("INSERT INTO rules (user_id, name, enabled, match, action, created_at) VALUES (?,?,?,?,?,?)",
                       (auth.id, data.name.strip(), int(data.enabled), data.match.model_dump_json(),
                        data.action.model_dump_json(), now()))
    return rule_out(conn.execute("SELECT * FROM rules WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{rule_id}")
def patch_rule(rule_id: int, data: RulePatch, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if data.enabled is not None:
        conn.execute("UPDATE rules SET enabled = ? WHERE id = ? AND user_id = ?", (int(data.enabled), rule_id, auth.id))
    row = conn.execute("SELECT * FROM rules WHERE id = ? AND user_id = ?", (rule_id, auth.id)).fetchone()
    if row is None:
        raise HTTPException(404, "Regel nicht gefunden.")
    return rule_out(row)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("DELETE FROM rules WHERE id = ? AND user_id = ?", (rule_id, auth.id)).rowcount == 0:
        raise HTTPException(404, "Regel nicht gefunden.")
