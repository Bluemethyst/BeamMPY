from collections import defaultdict, deque
import hmac
import secrets
import threading
import time

from flask import Blueprint, jsonify, request, session
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .errors import PanelError


def json_body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise PanelError("A JSON object is required.")
    return value


def credentials(value):
    username, password = value.get("username"), value.get("password")
    if not isinstance(username, str) or not 1 <= len(username.strip()) <= 80:
        raise PanelError("Username must contain 1–80 characters.")
    if not isinstance(password, str) or not 1 <= len(password) <= 1024:
        raise PanelError("Password is required and must be at most 1024 characters.")
    return username.strip(), password


class User(UserMixin):
    def __init__(self, row):
        self.id = str(row["id"])
        self.username = row["username"]


def register_auth(app, store, revoke_sockets):
    login_manager = LoginManager(app)
    api = Blueprint("auth", __name__, url_prefix="/api/auth")
    attempts = defaultdict(deque)
    attempts_lock = threading.Lock()

    def valid_token(token):
        if not isinstance(token, str):
            return False
        with store.connection() as db:
            return db.execute("SELECT 1 FROM auth_sessions WHERE token=?", (token,)).fetchone() is not None

    app.extensions["valid_token"] = valid_token

    @login_manager.user_loader
    def load_user(user_id):
        if not valid_token(session.get("auth_token")):
            return None
        with store.connection() as db:
            row = db.execute("SELECT id,username FROM users WHERE id=?", (user_id,)).fetchone()
        return User(row) if row else None

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
        return jsonify(user={"id": current_user.id, "username": current_user.username} if current_user.is_authenticated else None,
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
        login_user(User(row))

    @api.get("/session")
    def get_session():
        return response()

    @api.post("/setup")
    def setup():
        username, password = credentials(json_body())
        if len(password) < 12:
            raise PanelError("Choose an administrator password of at least 12 characters.")
        password_hash = generate_password_hash(password)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise PanelError("Initial setup is already complete.", 409)
            cursor = db.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password_hash))
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
        if not row or not check_password_hash(row["password"], password):
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

    app.register_blueprint(api)
