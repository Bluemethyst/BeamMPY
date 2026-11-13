from collections import defaultdict, deque
import hmac
import secrets
import threading
import time

from flask import Blueprint, jsonify, request, session
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .errors import PanelError
from .permissions import grants_for


def json_body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise PanelError("A JSON object is required.")
    return value


def credentials(value):
    username, password = value.get("username"), value.get("password")
    if not isinstance(username, str) or not 1 <= len(username.strip()) <= 80 or "\x00" in username:
        raise PanelError("Username must contain 1–80 characters.")
    if not isinstance(password, str) or not 1 <= len(password) <= 1024:
        raise PanelError("Password is required and must be at most 1024 characters.")
    return username.strip(), password


class User(UserMixin):
    def __init__(self, row, permissions):
        self.id = str(row["id"])
        self.username = row["username"]
        self.is_admin = bool(row["is_admin"])
        self.can_create_servers = bool(row["can_create_servers"])
        self.must_change_password = bool(row["must_change_password"])
        self.permissions = permissions

    def can(self, permission, server_id=None):
        if self.must_change_password:
            return False
        return self.is_admin or (self.can_create_servers if permission == "create_servers"
                                 else permission in self.permissions.get(server_id, []))

    def public(self):
        return {"id": self.id, "username": self.username, "is_admin": self.is_admin,
                "can_create_servers": self.can_create_servers, "must_change_password": self.must_change_password,
                "permissions": self.permissions}


def password_value(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 1024 or "\x00" in value:
        raise PanelError("Passwords must contain 8–1024 characters without null characters.")
    return value


def register_auth(app, store, revoke_sockets):
    login_manager = LoginManager(app)
    api = Blueprint("auth", __name__, url_prefix="/api/auth")
    attempts = defaultdict(deque)
    attempts_lock = threading.Lock()

    def valid_token(token):
        if not isinstance(token, str):
            return False
        with store.connection() as db:
            return db.execute("SELECT 1 FROM auth_sessions s JOIN users u ON u.id=s.user_id "
                              "WHERE s.token=? AND u.enabled=1", (token,)).fetchone() is not None

    app.extensions["valid_token"] = valid_token

    @login_manager.user_loader
    def load_user(user_id):
        if not valid_token(session.get("auth_token")):
            return None
        with store.connection() as db:
            row = db.execute("SELECT * FROM users WHERE id=? AND enabled=1", (user_id,)).fetchone()
            return User(row, grants_for(db, row["id"])) if row else None

    def token_user(token):
        with store.connection() as db:
            row = db.execute("SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id "
                             "WHERE s.token=? AND u.enabled=1", (token,)).fetchone()
            return User(row, grants_for(db, row["id"])) if row else None

    app.extensions["token_user"] = token_user

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error="Authentication required."), 401

    @app.before_request
    def csrf_protection():
        if request.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            provided = request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf_token", "")
            if not expected or not hmac.compare_digest(provided.encode(), expected.encode()):
                raise PanelError("Session verification failed. Refresh and try again.", 403)

    def response():
        with store.connection() as db:
            setup_required = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
        return jsonify(user=current_user.public() if current_user.is_authenticated else None,
                       setup_required=setup_required, csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32)))

    def establish(row):
        old_token = session.get("auth_token")
        if old_token:
            with store.connection() as db:
                db.execute("DELETE FROM auth_sessions WHERE token=?", (old_token,))
            revoke_sockets(old_token)
        session.clear()
        token = secrets.token_urlsafe(32)
        with store.connection() as db:
            db.execute("INSERT INTO auth_sessions(token,user_id) VALUES(?,?)", (token, row["id"]))
        session["auth_token"] = token
        session["csrf_token"] = secrets.token_urlsafe(32)
        with store.connection() as db:
            account = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
            login_user(User(account, grants_for(db, account["id"])))

    @api.get("/session")
    def get_session():
        return response()

    @api.post("/setup")
    def setup():
        username, password = credentials(json_body())
        password_value(password)
        password_hash = generate_password_hash(password)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise PanelError("Initial setup is already complete.", 409)
            cursor = db.execute("INSERT INTO users(username,password,is_admin) VALUES(?,?,1)", (username, password_hash))
            row = {"id": cursor.lastrowid, "username": username}
        establish(row)
        return response(), 201

    @api.post("/login")
    def login():
        username, password = credentials(json_body())
        address = request.remote_addr or "local"
        now = time.monotonic()
        with attempts_lock:
            # Prune inactive addresses so the rate-limit map remains bounded.
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 60:
                    del attempts[key]
            window = attempts[address]
            while window and window[0] < now - 60:
                window.popleft()
            if len(window) >= 10:
                raise PanelError("Too many login attempts. Try again in one minute.", 429)
            window.append(now)
        with store.connection() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not row["enabled"] or not check_password_hash(row["password"], password):
            raise PanelError("Invalid username or password.", 401)
        establish(row)
        return response()

    @api.post("/logout")
    @login_required
    def logout():
        token = session.get("auth_token")
        with store.connection() as db:
            db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        revoke_sockets(token)
        logout_user()
        session.clear()
        return response()

    def revoke_user(db, user_id):
        tokens = [row[0] for row in db.execute("SELECT token FROM auth_sessions WHERE user_id=?", (user_id,))]
        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        return tokens

    @api.post("/password")
    @login_required
    def change_password():
        body = json_body()
        password = password_value(body.get("new_password"))
        old = body.get("current_password")
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE id=?", (current_user.id,)).fetchone()
            if not isinstance(old, str) or len(old) > 1024 or not check_password_hash(row["password"], old):
                raise PanelError("Current password is incorrect.", 403)
            if check_password_hash(row["password"], password):
                raise PanelError("Choose a different password from your current password.")
            db.execute("UPDATE users SET password=?,must_change_password=0 WHERE id=?",
                       (generate_password_hash(password), current_user.id))
            tokens = revoke_user(db, current_user.id)
        for token in tokens:
            revoke_sockets(token)
        # A password change signs out every device, including this browser.
        logout_user()
        session.clear()
        return response()

    @api.post("/logout-all")
    @login_required
    def logout_all():
        with store.connection() as db:
            tokens = revoke_user(db, current_user.id)
        for token in tokens:
            revoke_sockets(token)
        logout_user()
        session.clear()
        return response()

    app.register_blueprint(api)
