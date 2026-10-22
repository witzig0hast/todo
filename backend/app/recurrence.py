"""Wiederholungen: nächste Fälligkeit in der Zeitzone des Benutzers berechnen (DST-sicher, Monatsende geklemmt)."""
import calendar
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_TZ = "Europe/Berlin"


class Recurrence(BaseModel):
    freq: Literal["daily", "weekdays", "weekly", "monthly", "yearly"]
    interval: int = Field(default=1, ge=1, le=365)
    after_done: bool = False  # nächste Fälligkeit ab Erledigung statt ab alter Fälligkeit


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc)


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def user_tz(conn: sqlite3.Connection, user_id: int) -> ZoneInfo:
    row = conn.execute("SELECT tz FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return zone(row["tz"] if row else None)


def _add_months(dt: datetime, months: int) -> datetime:
    m = dt.month - 1 + months
    year, month = dt.year + m // 12, m % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _step(dt: datetime, rec: Recurrence) -> datetime:
    """Ein Schritt in lokaler Wanduhrzeit (naiv), damit 9:00 auch nach der Zeitumstellung 9:00 bleibt."""
    if rec.freq == "daily":
        return dt + timedelta(days=rec.interval)
    if rec.freq == "weekly":
        return dt + timedelta(weeks=rec.interval)
    if rec.freq == "monthly":
        return _add_months(dt, rec.interval)
    if rec.freq == "yearly":
        return _add_months(dt, 12 * rec.interval)
    nxt = dt + timedelta(days=1)  # weekdays: nächster Mo-Fr
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def next_due(rec: Recurrence, due_at: str | None, done_at: str, tz: ZoneInfo, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    done_local = parse_utc(done_at).astimezone(tz).replace(tzinfo=None)
    if due_at:
        due_local = parse_utc(due_at).astimezone(tz).replace(tzinfo=None)
    else:  # ohne Fälligkeit: ab Erledigung, 9:00 Uhr
        due_local = done_local.replace(hour=9, minute=0, second=0)
    if rec.after_done:
        base = done_local.replace(hour=due_local.hour, minute=due_local.minute, second=0)
        nxt = _step(base, rec)
    else:
        nxt = _step(due_local, rec)
        # Verpasste Termine überspringen: die nächste liegt immer in der Zukunft
        guard = 0
        while nxt.replace(tzinfo=tz) <= now and guard < 5000:
            nxt = _step(nxt, rec)
            guard += 1
    return nxt.replace(tzinfo=tz).astimezone(timezone.utc).strftime(FMT)


def describe(rec: Recurrence) -> str:
    unit = {"daily": ("Tag", "Tage"), "weekly": ("Woche", "Wochen"), "monthly": ("Monat", "Monate"),
            "yearly": ("Jahr", "Jahre")}
    if rec.freq == "weekdays":
        text = "Werktags"
    elif rec.interval == 1:
        text = {"daily": "Täglich", "weekly": "Wöchentlich", "monthly": "Monatlich", "yearly": "Jährlich"}[rec.freq]
    else:
        text = f"Alle {rec.interval} {unit[rec.freq][1]}"
    return text + (" (ab Erledigung)" if rec.after_done else "")
