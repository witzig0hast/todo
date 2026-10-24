"""Weitere KI-Werkzeuge: Foto -> Aufgaben (Vision-Modell), Wochenplanung, semantische Suche (Embeddings), Duplikate,
Tag-/Listen-Vorschläge. Wie überall gilt: die KI schlägt vor, ausgeführt wird erst nach Bestätigung."""
import base64
import hashlib
import logging
import math
import re
import sqlite3
from array import array
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import config, ollama
from .ai_api import SYSTEM_GUARD, Ctx, _ai, _model
from .assistant import ACTION_SPEC, _context, normalize_actions
from .db import get_db, session
from .security import Auth, enforce_rate, get_auth
from .todos import get_todo, list_todos, normalize_tags

log = logging.getLogger("todo.ai_tools")
router = APIRouter(prefix="/api/ai", tags=["ai-tools"])
MAX_PHOTO = 10 * 1024 * 1024
EMBED_BATCH = 32
EMBED_PER_REQUEST = 256


def _setting(conn: sqlite3.Connection, user_id: int, key: str, default: str) -> str:
    row = conn.execute(f"SELECT {key} FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return row[key] if row and row[key] else default


# ------------------------------------------------------------------ Foto -> Aufgaben
@router.post("/photo")
async def photo(request: Request, now_local: str = Query(max_length=32), tz_offset: int = Query(ge=-840, le=840),
                auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Bild (Zettel, Brief, Rechnung, Plakat …) -> vorgeschlagene Aufgaben. Das Bild wird nicht gespeichert."""
    from .attachments import sniff

    enforce_rate(f"ai-photo:{auth.id}", 10, 60)
    data = await request.body()
    if not data or len(data) > MAX_PHOTO:
        raise HTTPException(413, "Bild fehlt oder ist größer als 10 MB.")
    if sniff(data[:64]) not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        raise HTTPException(415, "Bitte ein Foto (JPEG, PNG, WebP) senden.")
    ctx = Ctx(now_local=now_local, tz_offset=tz_offset)
    task = ("Der Nutzer hat ein Foto geschickt (z. B. Notizzettel, Brief, Rechnung, Einladung, Whiteboard). Lies den Inhalt "
            "und leite daraus konkrete Aufgaben ab - nur 'create'-Aktionen. Fristen, Termine und Zahlungsziele als due_at, "
            "wichtige Details (Beträge, Aktenzeichen, Adressen) in notes. Erfinde nichts, was nicht auf dem Bild steht. "
            'Antworte NUR mit JSON: {"reply": ein Satz, was auf dem Bild ist, "actions": [...]}.')
    system = f"{SYSTEM_GUARD}\nAktuelle lokale Zeit des Nutzers: {ctx.now_local}.\n{task}\n{ACTION_SPEC}"
    model = _setting(conn, auth.id, "vision_model", config.OLLAMA_VISION_MODEL)
    out = await _ai(ollama.chat_json(model, [{"role": "system", "content": system},
                                            {"role": "user", "content": "Welche Aufgaben ergeben sich aus diesem Bild?",
                                             "images": [base64.b64encode(data).decode()]}]))
    actions = [a for a in normalize_actions(conn, auth.id, out.get("actions"), tz_offset) if a["type"] == "create"]
    return {"reply": str(out.get("reply") or "")[:1000], "actions": actions}


# ------------------------------------------------------------------ Wochenplanung
@router.post("/weekplan")
async def weekplan(data: Ctx, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"ai:{auth.id}", 30, 60)
    task = ("Plane die nächsten 7 Tage: Verteile offene Aufgaben sinnvoll auf die Tage (höchstens 5 pro Tag, Wochenende "
            "leichter). Überfällige und hohe Priorität zuerst, Fristen nie nach hinten schieben, Aufgaben mit fester Uhrzeit "
            "(Termine) nicht verschieben. Nur 'reschedule'-Aktionen mit Datum und sinnvoller Uhrzeit, höchstens 10. "
            'Antworte NUR mit JSON: {"reply": kurze Begründung des Plans, "actions": [...]}.')
    system = (f"{SYSTEM_GUARD}\nAktuelle lokale Zeit des Nutzers: {data.now_local}.\n{task}\n{ACTION_SPEC}\n"
              f"{_context(conn, auth.id, data.tz_offset)}")
    out = await _ai(ollama.chat_json(_model(conn, auth.id), [{"role": "system", "content": system},
                                                             {"role": "user", "content": "Plane meine Woche."}]))
    actions = [a for a in normalize_actions(conn, auth.id, out.get("actions"), data.tz_offset) if a["type"] == "reschedule"]
    return {"reply": str(out.get("reply") or "")[:2000], "actions": actions}


# ------------------------------------------------------------------ Semantische Suche
def _text(t: dict) -> str:
    return " ".join(filter(None, [t["title"], (t.get("notes") or "")[:500], " ".join("#" + g for g in t.get("tags") or [])]))


def _norm(vec: list[float]) -> array:
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return array("f", (x / n for x in vec))


def _missing(conn: sqlite3.Connection, todos: list[dict], model: str) -> list[tuple[int, str, str]]:
    have: dict[int, tuple[str, str]] = {}
    ids = [t["id"] for t in todos]
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in conn.execute(f"SELECT todo_id, model, hash FROM todo_embeddings WHERE todo_id IN ({','.join('?' * len(part))})", part):
            have[r["todo_id"]] = (r["model"], r["hash"])
    out = []
    for t in todos:
        text = _text(t)
        h = hashlib.sha1(text.encode()).hexdigest()
        if have.get(t["id"]) != (model, h):
            out.append((t["id"], h, text))
    return out


def _store(conn: sqlite3.Connection, model: str, items: list[tuple[int, str, str]], vecs: list[list[float]]) -> None:
    for (tid, h, _), v in zip(items, vecs):
        conn.execute("INSERT OR REPLACE INTO todo_embeddings (todo_id, model, hash, vec) VALUES (?,?,?,?)",
                     (tid, model, h, _norm(v).tobytes()))


@router.get("/search")
async def semantic_search(q: str = Query(min_length=2, max_length=200), auth: Auth = Depends(get_auth),
                          conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"ai-search:{auth.id}", 30, 60)
    model = _setting(conn, auth.id, "embed_model", config.OLLAMA_EMBED_MODEL)
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (auth.id,))
    conn.execute("UPDATE user_settings SET semantic_used = 1 WHERE user_id = ?", (auth.id,))
    todos = list_todos(conn, auth.id, limit=5000)
    missing = _missing(conn, todos, model)
    todo_batch = missing[:EMBED_PER_REQUEST]
    for i in range(0, len(todo_batch), EMBED_BATCH):
        chunk = todo_batch[i:i + EMBED_BATCH]
        _store(conn, model, chunk, await _ai(ollama.embed(model, [c[2] for c in chunk])))
    qv = _norm((await _ai(ollama.embed(model, [q])))[0])
    ids = [t["id"] for t in todos]
    vecs = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in conn.execute(f"SELECT todo_id, vec FROM todo_embeddings WHERE model = ? AND todo_id IN ({','.join('?' * len(part))})",
                              (model, *part)):
            v = array("f")
            v.frombytes(r["vec"])
            if len(v) == len(qv):
                vecs[r["todo_id"]] = v
    scored = sorted(((sum(a * b for a, b in zip(qv, v)), tid) for tid, v in vecs.items()), reverse=True)
    return {"results": [{"id": tid, "score": round(score, 3)} for score, tid in scored[:15] if score >= 0.45],
            "pending": max(0, len(missing) - len(todo_batch)), "model": model}


def index_embeddings() -> None:
    """Hintergrund (jede Minute): fehlende Embeddings für Nutzer nachziehen, die die semantische Suche verwenden."""
    with session() as conn:
        users = conn.execute("SELECT s.user_id, s.embed_model FROM user_settings s JOIN users u ON u.id = s.user_id "
                             "WHERE s.semantic_used = 1 AND u.status = 'approved'").fetchall()
        for u in users:
            model = u["embed_model"] or config.OLLAMA_EMBED_MODEL
            missing = _missing(conn, list_todos(conn, u["user_id"], limit=5000), model)[:EMBED_BATCH * 2]
            for i in range(0, len(missing), EMBED_BATCH):
                chunk = missing[i:i + EMBED_BATCH]
                try:
                    _store(conn, model, chunk, ollama.embed_sync(model, [c[2] for c in chunk]))
                except ollama.OllamaError as exc:
                    log.info("Embeddings übersprungen: %s", exc)
                    return


# ------------------------------------------------------------------ Duplikate (ohne KI-Modell, sofort)
_WORD = re.compile(r"[\wäöüß]+", re.IGNORECASE)


STOP = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "und", "oder", "für", "fuer", "mit",
        "am", "im", "beim", "zum", "zur", "von", "vom", "an", "auf", "in", "zu", "noch", "mal", "bitte", "the", "a", "to"}


def _tokens(s: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(s) if w.lower() not in STOP]


def similar(a: str, b: str) -> float:
    """0..1 - Wortgleichheit (Reihenfolge egal, Füllwörter ignoriert) oder Zeichenähnlichkeit, je nachdem was höher ist."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    common = len(sa & sb)
    words = 0.0
    if min(len(sa), len(sb)) >= 2:
        words = max(common / len(sa | sb), 0.9 * common / min(len(sa), len(sb)))
    m = SequenceMatcher(None, " ".join(ta), " ".join(tb))
    if m.real_quick_ratio() < 0.6:
        return words
    chars = m.ratio()
    if min(len(sa), len(sb)) >= 2:  # „Mama anrufen“ ≠ „Papa anrufen“: unterschiedliche Wörter dämpfen die Zeichenähnlichkeit
        chars *= 0.85 + 0.15 * common / len(sa | sb)
    return max(words, chars)


class DupIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    exclude_id: int | None = None


@router.post("/duplicates")
def duplicates(data: DupIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    hits = []
    for t in list_todos(conn, auth.id, done=False, limit=2000):
        if t["id"] == data.exclude_id or t["parent_id"]:
            continue
        score = similar(data.title, t["title"])
        if score >= 0.82:
            hits.append({"id": t["id"], "title": t["title"], "score": round(score, 2)})
    return {"duplicates": sorted(hits, key=lambda x: -x["score"])[:3]}


@router.get("/duplicates/all")
def all_duplicates(auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"ai-dups:{auth.id}", 10, 60)
    todos = [t for t in list_todos(conn, auth.id, done=False, limit=800) if not t["parent_id"]]
    pairs = []
    for i, a in enumerate(todos):
        for b in todos[i + 1:]:
            score = similar(a["title"], b["title"])
            if score >= 0.82:
                pairs.append({"a": {"id": a["id"], "title": a["title"], "created_at": a["created_at"]},
                              "b": {"id": b["id"], "title": b["title"], "created_at": b["created_at"]}, "score": round(score, 2)})
    return {"pairs": sorted(pairs, key=lambda p: -p["score"])[:50]}


# ------------------------------------------------------------------ Tags & Liste vorschlagen
class SuggestIn(BaseModel):
    todo_id: int


@router.post("/suggest")
async def suggest(data: SuggestIn, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    enforce_rate(f"ai:{auth.id}", 30, 60)
    t = get_todo(conn, auth.id, data.todo_id)
    counts: dict[str, int] = {}
    for r in conn.execute("SELECT tags FROM todos WHERE user_id = ? AND tags != ''", (auth.id,)):
        for g in r["tags"].split(","):
            if g:
                counts[g] = counts.get(g, 0) + 1
    known = [g for g, _ in sorted(counts.items(), key=lambda x: -x[1])[:40]]
    lists = {r["name"].lower(): r["id"] for r in conn.execute(
        "SELECT id, name FROM lists WHERE user_id = :u OR id IN (SELECT list_id FROM list_members WHERE user_id = :u)", {"u": auth.id})}
    system = (f"{SYSTEM_GUARD}\nOrdne die Aufgabe ein. Bevorzuge vorhandene Tags: {', '.join(known) or '(keine)'}. "
              f"Vorhandene Listen: {', '.join(lists) or '(keine)'}. Höchstens 3 Tags (kurz, klein, ohne #); Liste nur, "
              'wenn eine eindeutig passt. Antworte NUR mit JSON: {"tags": [...], "list": Name oder null}.')
    out = await _ai(ollama.chat_json(_model(conn, auth.id), [
        {"role": "system", "content": system}, {"role": "user", "content": f"Aufgabe: {t['title']}\nNotizen: {(t['notes'] or '')[:1000]}"}]))
    tags = []
    for g in (out.get("tags") or [])[:5] if isinstance(out.get("tags"), list) else []:
        try:
            tags += normalize_tags([str(g).replace(" ", "-")])
        except ValueError:
            continue
    have = [g for g in (t["tags"] or "").split(",") if g]
    tags = [g for g in dict.fromkeys(tags) if g not in have][:3]
    lst = lists.get(str(out.get("list") or "").strip().lower())
    return {"tags": tags, "list_id": lst if lst != t["list_id"] else None}
