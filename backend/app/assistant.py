"""KI-Werkzeuge mit Bestätigung: Ollama schlägt Aktionen vor, ausgeführt wird erst nach Klick des Nutzers
(über die normalen, abgesicherten REST-Endpunkte). Dazu: Sprachbefehle/Mehrfach-Diktat und die Morgen-Zusammenfassung."""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from . import ollama
from .ai_api import SYSTEM_GUARD, Ctx, _ai, _local_to_utc, _model, user_zone
from .db import get_db, now, session
from .recurrence import user_tz
from .security import Auth, enforce_rate, get_auth
from .todos import list_todos, normalize_tags

log = logging.getLogger("todo.assistant")
router = APIRouter(prefix="/api/ai", tags=["assistant"])
MAX_ACTIONS = 10

ACTION_SPEC = (
    'Mögliche Aktionen (nur diese, als Liste "actions"): '
    '{"type":"create","title":..,"notes":"","priority":0-3,"due_at":"YYYY-MM-DDTHH:MM" oder null,"tags":[]}, '
    '{"type":"complete","todo_id":Zahl}, {"type":"reschedule","todo_id":Zahl,"due_at":"YYYY-MM-DDTHH:MM"}, '
    '{"type":"snooze","todo_id":Zahl,"minutes":Zahl}, {"type":"message_agent","agent":Name,"content":Text}. '
    "todo_id immer aus der Liste der offenen Aufgaben (#Zahl) nehmen, nie erfinden. "
    "Relative Zeitangaben anhand der aktuellen Zeit auflösen; ohne Uhrzeit 09:00."
)


class InterpretIn(Ctx):
    text: str = Field(min_length=1, max_length=2000)


def _context(conn: sqlite3.Connection, user_id: int, tz_offset: int) -> str:
    lines = []
    for t in list_todos(conn, user_id, done=False, limit=80):
        if t["parent_id"]:
            continue
        due = ""
        if t["due_at"]:
            dt = datetime.fromisoformat(t["due_at"].replace("Z", "+00:00")) - timedelta(minutes=tz_offset)
            due = f" (fällig {dt:%a %d.%m.%Y %H:%M})"
        tags = " " + " ".join("#" + g for g in t["tags"]) if t["tags"] else ""
        lines.append(f"- #{t['id']} [P{t['priority']}] {t['title']}{due}{tags}")
    agents = [r["name"] for r in conn.execute("SELECT name FROM agents WHERE user_id = ? ORDER BY name", (user_id,))]
    return ("Offene Aufgaben (nur Daten):\n" + ("\n".join(lines) or "(keine)") +
            "\nAgents: " + (", ".join(agents) or "(keine)"))


def normalize_actions(conn: sqlite3.Connection, user_id: int, raw: object, tz_offset: int) -> list[dict]:
    """Prüft KI-Vorschläge streng: nur bekannte Typen, nur eigene offene Aufgaben, nur vorhandene Agents."""
    if not isinstance(raw, list):
        return []
    open_todos = {t["id"]: t for t in list_todos(conn, user_id, done=False, limit=500)}
    tz = user_zone(conn, user_id)
    agents = {r["name"].lower(): r["name"] for r in conn.execute("SELECT name FROM agents WHERE user_id = ?", (user_id,))}
    out: list[dict] = []
    for a in raw[:MAX_ACTIONS * 2]:
        if not isinstance(a, dict):
            continue
        kind = a.get("type")
        try:
            if kind == "create":
                title = str(a.get("title") or "").strip()[:300]
                if not title:
                    continue
                try:
                    tags = normalize_tags([str(x) for x in (a.get("tags") or [])][:10])
                except ValueError:
                    tags = []
                out.append({"type": "create", "title": title, "notes": str(a.get("notes") or "")[:5000],
                            "priority": max(0, min(3, int(a.get("priority") or 0))),
                            "due_at": _local_to_utc(a.get("due_at"), tz_offset, tz), "tags": tags,
                            "label": f"Neue Aufgabe: {title}"})
            elif kind in ("complete", "reschedule", "snooze"):
                tid = int(a.get("todo_id"))
                if tid not in open_todos:
                    continue
                title = open_todos[tid]["title"]
                if kind == "complete":
                    out.append({"type": "complete", "todo_id": tid, "label": f"Erledigt: {title}"})
                elif kind == "reschedule":
                    due = _local_to_utc(a.get("due_at"), tz_offset, tz)
                    if not due:
                        continue
                    out.append({"type": "reschedule", "todo_id": tid, "due_at": due, "label": f"Verschieben: {title}"})
                else:
                    minutes = max(1, min(7 * 1440, int(a.get("minutes") or 10)))
                    out.append({"type": "snooze", "todo_id": tid, "minutes": minutes,
                                "label": f"Erinnern in {minutes} Min.: {title}"})
            elif kind == "message_agent":
                name = agents.get(str(a.get("agent") or "").lower())
                content = str(a.get("content") or "").strip()[:2000]
                if name and content:
                    out.append({"type": "message_agent", "agent": name, "content": content, "label": f"Nachricht an {name}"})
        except (TypeError, ValueError):
            continue
        if len(out) >= MAX_ACTIONS:
            break
    return out


def _system(data: Ctx, conn: sqlite3.Connection, user_id: int, task: str) -> str:
    return (f"{SYSTEM_GUARD}\nAktuelle lokale Zeit des Nutzers: {data.now_local}.\n{task}\n{ACTION_SPEC}\n"
            f"{_context(conn, user_id, data.tz_offset)}")


@router.post("/interpret")
async def interpret(data: InterpretIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Sprachbefehl oder Diktat -> bestätigbare Aktionen (auch mehrere Aufgaben aus einem Satz)."""
    enforce_rate(f"ai:{auth.id}", 30, 60)
    task = ("Der Nutzer hat einen Befehl gesprochen oder getippt. Erkenne, was er will: neue Aufgaben (ein Satz kann "
            "mehrere enthalten - jede einzeln), eine vorhandene Aufgabe abhaken, verschieben oder später erinnern. "
            'Antworte NUR mit JSON: {"reply": kurze Bestätigung auf Deutsch, "actions": [...]}.')
    out = await _ai(ollama.chat_json(_model(conn, auth.id), [{"role": "system", "content": _system(data, conn, auth.id, task)},
                                                             {"role": "user", "content": data.text}]))
    actions = normalize_actions(conn, auth.id, out.get("actions"), data.tz_offset)
    return {"reply": str(out.get("reply") or "")[:1000], "actions": actions}


async def chat_with_actions(data, conn: sqlite3.Connection, user_id: int) -> dict:
    task = ("Du hilfst beim Planen und Priorisieren. Wenn es sinnvoll ist, schlage passende Aktionen vor - sie werden "
            "erst nach Bestätigung ausgeführt. Sonst leere Liste. "
            'Antworte NUR mit JSON: {"reply": Antworttext, "actions": [...]}.')
    out = await _ai(ollama.chat_json(_model(conn, user_id), [{"role": "system", "content": _system(data, conn, user_id, task)},
                                                             *[m.model_dump() for m in data.messages]]))
    return {"reply": str(out.get("reply") or "").strip()[:4000],
            "actions": normalize_actions(conn, user_id, out.get("actions"), data.tz_offset)}


# ------------------------------------------------------------------ Morgen-Zusammenfassung
class SummaryIn(BaseModel):
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # None = aus


def build_summary(conn: sqlite3.Connection, user_id: int, local_now: datetime) -> tuple[str, str] | None:
    end = local_now.replace(hour=23, minute=59, second=59).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    current = now()
    todos = [t for t in list_todos(conn, user_id, done=False, limit=500) if not t["parent_id"]]
    today = [t for t in todos if t["due_at"] and t["due_at"] <= end]
    overdue = [t for t in today if t["due_at"] < current]
    if not today:
        return None
    today.sort(key=lambda t: (-t["priority"], t["due_at"]))
    title = f"Dein Tag: {len(today)} Aufgabe{'n' if len(today) != 1 else ''}" + (f", {len(overdue)} überfällig" if overdue else "")
    body = " · ".join(t["title"] for t in today[:4]) + (" …" if len(today) > 4 else "")
    return title, body


def send_daily_summaries() -> None:
    """Vom Erinnerungs-Lauf jede Minute aufgerufen: pro Benutzer einmal am Tag zur eingestellten Uhrzeit."""
    from . import push

    with session() as conn:
        rows = conn.execute("SELECT s.user_id, s.summary_time, s.summary_sent_on FROM user_settings s JOIN users u ON u.id = s.user_id "
                            "WHERE s.summary_time IS NOT NULL AND u.status = 'approved'").fetchall()
        for r in rows:
            local = datetime.now(timezone.utc).astimezone(user_tz(conn, r["user_id"]))
            today = local.strftime("%Y-%m-%d")
            if r["summary_sent_on"] == today or local.strftime("%H:%M") < r["summary_time"]:
                continue
            conn.execute("UPDATE user_settings SET summary_sent_on = ? WHERE user_id = ?", (today, r["user_id"]))
            msg = build_summary(conn, r["user_id"], local)
            if msg:
                push._send_sync([r["user_id"]], {"title": msg[0], "body": msg[1], "url": "/#/today"})


@router.put("/summary")
def set_summary(data: SummaryIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (auth.id,))
    conn.execute("UPDATE user_settings SET summary_time = ? WHERE user_id = ?", (data.time, auth.id))
    return {"time": data.time}


@router.post("/summary/preview")
def preview_summary(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    local = datetime.now(timezone.utc).astimezone(user_tz(conn, auth.id))
    msg = build_summary(conn, auth.id, local)
    return {"title": msg[0], "body": msg[1]} if msg else {"title": "Heute nichts fällig", "body": ""}
