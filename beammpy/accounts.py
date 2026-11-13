"""Administrator-managed members; there is no public registration."""
import json
import sqlite3

from flask import Blueprint, jsonify
from flask_login import login_required
from werkzeug.security import generate_password_hash

from .auth import json_body, password_value
from .errors import PanelError
from .permissions import PERMISSIONS, grants_for, require_admin


def register_accounts(app, store, revoke_sockets):
    api = Blueprint("accounts", __name__, url_prefix="/api/users")

    @api.before_request
    @login_required
    def authenticate():
        require_admin()

    def public(db, row):
        return {"id": str(row["id"]), "username": row["username"], "is_admin": bool(row["is_admin"]),
                "enabled": bool(row["enabled"]), "can_create_servers": bool(row["can_create_servers"]),
                "must_change_password": bool(row["must_change_password"]), "permissions": grants_for(db, row["id"])}

    def validate(db, body):
        allowed = {"username", "password", "temporary", "enabled", "can_create_servers", "permissions"}
        if body.keys() - allowed:
            raise PanelError("Unsupported account fields.")
        username = body.get("username")
        if not isinstance(username, str) or not 1 <= len(username.strip()) <= 80 or "\x00" in username:
            raise PanelError("Username must contain 1–80 characters without null characters.")
        for key in ("enabled", "can_create_servers"):
            if type(body.get(key, key == "enabled")) is not bool:
                raise PanelError(f"{key} must be a boolean.")
        grants = body.get("permissions", {})
        if not isinstance(grants, dict):
            raise PanelError("Permissions must be an object keyed by server ID.")
        for server_id, values in grants.items():
            if (not isinstance(values, list) or any(not isinstance(value, str) or value not in PERMISSIONS for value in values)
                    or len(values) != len(set(values))):
                raise PanelError("Unknown or duplicate server permissions.")
            if "console_command" in values and "console_view" not in values:
                raise PanelError("Console commands also require console viewing permission.")
            if not db.execute("SELECT 1 FROM servers WHERE id=?", (server_id,)).fetchone():
                raise PanelError("An assigned server no longer exists.", 409)
        return username.strip(), grants

    def temporary_password(body):
        value = body.get("temporary", True)
        if type(value) is not bool:
            raise PanelError("temporary must be a boolean.")
        return value

    def save_grants(db, user_id, grants):
        db.execute("DELETE FROM server_grants WHERE user_id=?", (user_id,))
        db.executemany("INSERT INTO server_grants(user_id,server_id,permissions) VALUES(?,?,?)",
                       [(user_id, key, json.dumps(values)) for key, values in grants.items()])

    def revoke(db, user_id):
        tokens = [row[0] for row in db.execute("SELECT token FROM auth_sessions WHERE user_id=?", (user_id,))]
        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        return tokens

    def member(db, user_id):
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise PanelError("Account not found.", 404)
        if row["is_admin"]:
            raise PanelError("The administrator manages their password from My account; this account cannot be disabled, deleted or reassigned.", 403)
        return row

    @api.get("")
    def users():
        with store.connection() as db:
            return jsonify(users=[public(db, row) for row in db.execute("SELECT * FROM users ORDER BY id")],
                           permissions=list(PERMISSIONS))

    @api.post("")
    def create():
        body = json_body()
        password = password_value(body.get("password"))
        temporary = temporary_password(body)
        try:
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                username, grants = validate(db, body)
                cursor = db.execute("INSERT INTO users(username,password,enabled,can_create_servers,must_change_password) "
                                    "VALUES(?,?,?,?,?)", (username, generate_password_hash(password), body.get("enabled", True),
                                                         body.get("can_create_servers", False), temporary))
                save_grants(db, cursor.lastrowid, grants)
                result = public(db, db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise PanelError("That username is already in use.", 409) from exc
        return jsonify(user=result), 201

    @api.put("/<int:user_id>")
    def update(user_id):
        body = json_body()
        if "password" in body or "temporary" in body:
            raise PanelError("Use Reset password to change the password and its temporary status.")
        try:
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                member(db, user_id)
                username, grants = validate(db, body)
                db.execute("UPDATE users SET username=?,enabled=?,can_create_servers=? WHERE id=?",
                           (username, body.get("enabled", True), body.get("can_create_servers", False), user_id))
                save_grants(db, user_id, grants)
                tokens = revoke(db, user_id)
                result = public(db, db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise PanelError("That username is already in use.", 409) from exc
        for token in tokens:
            revoke_sockets(token)
        return jsonify(user=result)

    @api.post("/<int:user_id>/password")
    def reset(user_id):
        body = json_body()
        if body.keys() - {"password", "temporary"}:
            raise PanelError("Unsupported password fields.")
        password = password_value(body.get("password"))
        temporary = temporary_password(body)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            member(db, user_id)
            db.execute("UPDATE users SET password=?,must_change_password=? WHERE id=?",
                       (generate_password_hash(password), temporary, user_id))
            tokens = revoke(db, user_id)
        for token in tokens:
            revoke_sockets(token)
        return jsonify(reset=True)

    @api.delete("/<int:user_id>")
    def delete(user_id):
        body = json_body()
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = member(db, user_id)
            if body.get("confirmation") != row["username"]:
                raise PanelError("Account confirmation does not match. Refresh the user list and try again.", 409)
            tokens = revoke(db, user_id)
            # Grants cascade; server registrations and their files are retained.
            db.execute("DELETE FROM users WHERE id=?", (user_id,))
        for token in tokens:
            revoke_sockets(token)
        return jsonify(deleted=True)

    app.register_blueprint(api)
