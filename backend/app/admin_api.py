import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from . import events, push
from .db import audit, get_db, now, tx
from .security import Auth, client_ip, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

ACTIONS = {"approve": "approved", "reject": "rejected", "block": "blocked", "unblock": "approved"}


@router.get("/users")
def users(_: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT id, username, role, status, created_at, approved_at FROM users ORDER BY "
                        "CASE status WHEN 'pending' THEN 0 ELSE 1 END, id")
    return {"users": [dict(r) for r in rows]}


def _target(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Benutzer nicht gefunden.")
    return row


def _last_admin(conn: sqlite3.Connection, user_id: int) -> bool:
    return conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND status='approved' AND id != ?",
                        (user_id,)).fetchone()[0] == 0


@router.post("/users/{user_id}/{action}")
def user_action(user_id: int, action: str, request: Request, admin: Auth = Depends(require_admin),
                conn: sqlite3.Connection = Depends(get_db)):
    if action not in ACTIONS and action not in ("promote", "demote"):
        raise HTTPException(404, "Unbekannte Aktion.")
    with tx(conn):
        target = _target(conn, user_id)
        if action in ("promote", "demote"):
            if target["status"] != "approved":
                raise HTTPException(422, "Nur freigegebene Benutzer können die Rolle wechseln.")
            if action == "demote" and target["role"] == "admin" and _last_admin(conn, user_id):
                raise HTTPException(422, "Der letzte Administrator kann nicht herabgestuft werden.")
            conn.execute("UPDATE users SET role = ? WHERE id = ?", ("admin" if action == "promote" else "user", user_id))
        else:
            if action in ("reject", "block") and target["role"] == "admin" and _last_admin(conn, user_id):
                raise HTTPException(422, "Der letzte Administrator kann nicht gesperrt werden.")
            if action in ("reject", "block") and user_id == admin.id:
                raise HTTPException(422, "Du kannst dich nicht selbst sperren.")
            status = ACTIONS[action]
            conn.execute("UPDATE users SET status = ?, approved_at = ? WHERE id = ?",
                         (status, now() if status == "approved" else None, user_id))
            if status != "approved":
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        audit(conn, admin.user["username"], f"admin_{action}", target["username"], admin.id, client_ip(request))
    if action == "approve":
        push.notify_threadsafe([user_id], "Konto freigegeben", "Du kannst dich jetzt anmelden.")
    row = _target(conn, user_id)
    return {k: row[k] for k in ("id", "username", "role", "status")}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, admin: Auth = Depends(require_admin),
                conn: sqlite3.Connection = Depends(get_db)):
    with tx(conn):
        target = _target(conn, user_id)
        if user_id == admin.id:
            raise HTTPException(422, "Du kannst dich nicht selbst löschen.")
        if target["role"] == "admin" and _last_admin(conn, user_id):
            raise HTTPException(422, "Der letzte Administrator kann nicht gelöscht werden.")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        audit(conn, admin.user["username"], "admin_delete", target["username"], admin.id, client_ip(request))
    events.publish("user", user_id, "admin", {"op": "deleted"})


@router.get("/audit")
def audit_log(_: Auth = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT at, actor, action, detail, ip FROM audit_log ORDER BY id DESC LIMIT 200")
    return {"entries": [dict(r) for r in rows]}
