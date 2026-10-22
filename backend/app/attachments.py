"""Dateianhänge an Aufgaben: Typ wird am Inhalt erkannt (nicht an Endung/Header), Größen- und Kontingentgrenzen,
Auslieferung mit Sandbox-CSP und nosniff. Dateien liegen unter DATA_DIR/attachments mit zufälligem Namen."""
import secrets
import sqlite3
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from . import config
from .db import get_db, now
from .security import Auth, enforce_rate, get_auth
from .todos import audience, get_todo

router = APIRouter(prefix="/api", tags=["attachments"])
MAX_FILE = 10 * 1024 * 1024
MAX_PER_USER = 200 * 1024 * 1024
MAX_PER_TODO = 20
INLINE = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}


def _dir():
    d = config.DATA_DIR / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def remove_file(stored_name: str) -> None:
    try:
        (_dir() / stored_name).unlink(missing_ok=True)
    except OSError:
        pass


def sniff(data: bytes) -> str | None:
    """Erlaubte Typen anhand der ersten Bytes. Alles andere (HTML, SVG, Programme, ...) wird abgelehnt."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    head = text.lstrip()[:200].lower()
    if head.startswith(("<", "<?xml", "<!doctype")) or "<script" in head:
        return None  # HTML/SVG/XML nicht als Text annehmen
    return "text/plain"


def _clean_name(name: str) -> str:
    name = unquote(name or "").replace("\\", "/").split("/")[-1]
    name = "".join(c for c in name if c.isprintable() and c not in '<>:"|?*').strip(" .")
    return (name or "datei")[:120]


def att_out(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "todo_id": r["todo_id"], "filename": r["filename"], "mime": r["mime"], "size": r["size"],
            "created_at": r["created_at"], "url": f"/api/attachments/{r['id']}"}


@router.get("/todos/{todo_id}/attachments")
def list_attachments(todo_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    get_todo(conn, auth.id, todo_id)
    rows = conn.execute("SELECT * FROM attachments WHERE todo_id = ? ORDER BY id", (todo_id,))
    return {"attachments": [att_out(r) for r in rows]}


@router.post("/todos/{todo_id}/attachments", status_code=201)
async def upload(todo_id: int, request: Request, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    """Rohdaten im Body, Dateiname im Header X-Filename (URL-kodiert)."""
    enforce_rate(f"upload:{auth.id}", 30, 300)
    todo = get_todo(conn, auth.id, todo_id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_FILE:
        raise HTTPException(413, "Datei zu groß (max. 10 MB).")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_FILE:
            raise HTTPException(413, "Datei zu groß (max. 10 MB).")
    if not data:
        raise HTTPException(422, "Leere Datei.")
    mime = sniff(bytes(data[:4096])) if len(data) > 4096 else sniff(bytes(data))
    if mime == "text/plain":
        try:
            bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            mime = None
    if mime is None:
        raise HTTPException(415, "Dateityp nicht erlaubt (Bilder, PDF oder Text).")
    used = conn.execute("SELECT COALESCE(SUM(size), 0) FROM attachments WHERE user_id = ?", (auth.id,)).fetchone()[0]
    if used + len(data) > MAX_PER_USER:
        raise HTTPException(413, "Speicherkontingent erschöpft (200 MB).")
    if conn.execute("SELECT COUNT(*) FROM attachments WHERE todo_id = ?", (todo_id,)).fetchone()[0] >= MAX_PER_TODO:
        raise HTTPException(422, f"Maximal {MAX_PER_TODO} Anhänge pro Aufgabe.")
    stored = secrets.token_hex(16)
    path = _dir() / stored
    path.write_bytes(bytes(data))
    path.chmod(0o600)
    cur = conn.execute("INSERT INTO attachments (todo_id, user_id, filename, mime, size, stored_name, created_at) VALUES (?,?,?,?,?,?,?)",
                       (todo_id, auth.id, _clean_name(request.headers.get("x-filename", "")), mime, len(data), stored, now()))
    from . import events

    for uid in audience(conn, todo):
        events.publish("user", uid, "todo", {"op": "attachments", "id": todo_id})
    return att_out(conn.execute("SELECT * FROM attachments WHERE id = ?", (cur.lastrowid,)).fetchone())


def _attachment(conn: sqlite3.Connection, user_id: int, attachment_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Anhang nicht gefunden.")
    get_todo(conn, user_id, row["todo_id"])  # Zugriff über die Aufgabe
    return row


@router.get("/attachments/{attachment_id}")
def download(attachment_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = _attachment(conn, auth.id, attachment_id)
    disposition = "inline" if row["mime"] in INLINE else "attachment"
    return FileResponse(_dir() / row["stored_name"], media_type=row["mime"], headers={
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row['filename'])}",
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox",
        "Cache-Control": "private, no-store"})


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete(attachment_id: int, auth: Auth = Depends(get_auth), conn: sqlite3.Connection = Depends(get_db)):
    row = _attachment(conn, auth.id, attachment_id)
    conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    remove_file(row["stored_name"])
