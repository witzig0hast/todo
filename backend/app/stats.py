"""Statistik & Wochenrückblick: erledigt pro Woche/Wochentag, Serie, Fokuszeit, Dauerbrenner – in der Zeitzone des Benutzers."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .db import get_db, now, session
from .recurrence import FMT, parse_utc, user_tz
from .security import Auth, get_auth

router = APIRouter(prefix="/api/stats", tags=["stats"])
WEEKS = 8
REVIEW_WEEKDAY, REVIEW_HOUR = 6, 18  # Sonntag 18 Uhr


def _local_day(iso: str, tz) -> date:
    return parse_utc(iso).astimezone(tz).date()


def compute(conn: sqlite3.Connection, user_id: int, now_utc: datetime | None = None) -> dict:
    tz = user_tz(conn, user_id)
    local_now = (now_utc or datetime.now(timezone.utc)).astimezone(tz)
    today = local_now.date()
    week_start = today - timedelta(days=today.weekday())
    first = week_start - timedelta(weeks=WEEKS - 1)
    since = datetime.combine(first, datetime.min.time(), tz).astimezone(timezone.utc).strftime(FMT)

    done = conn.execute("SELECT done_at, created_at, tags FROM todos WHERE user_id = ? AND done = 1 AND parent_id IS NULL "
                        "AND done_at >= ?", (user_id, since)).fetchall()
    focus = conn.execute("SELECT started_at, minutes FROM time_entries WHERE user_id = ? AND started_at >= ?", (user_id, since)).fetchall()
    weeks = [{"start": (first + timedelta(weeks=i)).isoformat(), "done": 0, "focus_min": 0} for i in range(WEEKS)]
    weekday = [0] * 7
    tags: dict[str, int] = {}
    durations = []
    month_ago = today - timedelta(days=30)
    for r in done:
        d = _local_day(r["done_at"], tz)
        weeks[min(WEEKS - 1, (d - first).days // 7)]["done"] += 1
        weekday[d.weekday()] += 1
        for t in (r["tags"] or "").split(","):
            if t:
                tags[t] = tags.get(t, 0) + 1
        if d >= month_ago:
            durations.append((parse_utc(r["done_at"]) - parse_utc(r["created_at"])).total_seconds() / 86400)
    for r in focus:
        d = _local_day(r["started_at"], tz)
        if d >= first:
            weeks[min(WEEKS - 1, (d - first).days // 7)]["focus_min"] += r["minutes"]
    # Serie: aufeinanderfolgende Tage mit mind. einer erledigten Aufgabe (heute zählt, muss aber noch nicht)
    all_days = {_local_day(r["done_at"], tz) for r in conn.execute(
        "SELECT done_at FROM todos WHERE user_id = ? AND done = 1 AND done_at IS NOT NULL", (user_id,))}
    streak, day = 0, today if today in all_days else today - timedelta(days=1)
    while day in all_days:
        streak += 1
        day -= timedelta(days=1)
    current = now()
    open_rows = conn.execute("SELECT id, title, due_at, created_at FROM todos WHERE user_id = ? AND done = 0 AND parent_id IS NULL",
                             (user_id,)).fetchall()
    overdue = sorted((r for r in open_rows if r["due_at"] and r["due_at"] < current), key=lambda r: r["due_at"])
    created_week = conn.execute("SELECT COUNT(*) FROM todos WHERE user_id = ? AND parent_id IS NULL AND created_at >= ?",
                                (user_id, datetime.combine(week_start, datetime.min.time(), tz).astimezone(timezone.utc).strftime(FMT))).fetchone()[0]
    return {
        "today": today.isoformat(),
        "week_done": weeks[-1]["done"], "last_week_done": weeks[-2]["done"],
        "week_focus_min": weeks[-1]["focus_min"], "created_this_week": created_week,
        "weeks": weeks, "weekday": weekday, "streak": streak,
        "open": len(open_rows), "overdue": len(overdue),
        "avg_days_to_done": round(sum(durations) / len(durations), 1) if durations else None,
        "top_tags": [{"name": k, "count": v} for k, v in sorted(tags.items(), key=lambda x: (-x[1], x[0]))[:6]],
        "longest_overdue": [{"id": r["id"], "title": r["title"], "due_at": r["due_at"]} for r in overdue[:5]],
    }


def _fmt_min(m: int) -> str:
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def review_message(s: dict) -> tuple[str, str]:
    diff = s["week_done"] - s["last_week_done"]
    title = f"Wochenrückblick: {s['week_done']} erledigt" + (f" ({'+' if diff > 0 else ''}{diff})" if diff else "")
    parts = []
    if s["streak"]:
        parts.append(f"Serie {s['streak']} Tag{'e' if s['streak'] != 1 else ''}")
    if s["week_focus_min"]:
        parts.append("Fokus " + _fmt_min(s["week_focus_min"]))
    parts.append(f"{s['open']} offen" + (f", {s['overdue']} überfällig" if s["overdue"] else ""))
    return title, " · ".join(parts)


def send_weekly_reviews() -> None:
    from . import push

    with session() as conn:
        rows = conn.execute("SELECT s.user_id, s.review_sent_on FROM user_settings s JOIN users u ON u.id = s.user_id "
                            "WHERE s.review_enabled = 1 AND u.status = 'approved'").fetchall()
        for r in rows:
            local = datetime.now(timezone.utc).astimezone(user_tz(conn, r["user_id"]))
            day = local.strftime("%Y-%m-%d")
            if local.weekday() != REVIEW_WEEKDAY or local.hour < REVIEW_HOUR or r["review_sent_on"] == day:
                continue
            conn.execute("UPDATE user_settings SET review_sent_on = ? WHERE user_id = ?", (day, r["user_id"]))
            title, body = review_message(compute(conn, r["user_id"]))
            push._send_sync([r["user_id"]], {"title": title, "body": body, "url": "/#/stats"})


class ReviewIn(BaseModel):
    enabled: bool


@router.get("")
def get_stats(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    out = compute(conn, auth.id)
    row = conn.execute("SELECT review_enabled FROM user_settings WHERE user_id = ?", (auth.id,)).fetchone()
    out["review_enabled"] = bool(row and row["review_enabled"])
    out["review_preview"] = dict(zip(("title", "body"), review_message(out)))
    return out


@router.put("/review")
def set_review(data: ReviewIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (auth.id,))
    conn.execute("UPDATE user_settings SET review_enabled = ? WHERE user_id = ?", (int(data.enabled), auth.id))
    return {"enabled": data.enabled}
