import atexit
import os
from pathlib import Path
import secrets

from dotenv import dotenv_values
from flask import Flask, jsonify, redirect, send_from_directory
from flask_socketio import SocketIO
import portalocker
from werkzeug.exceptions import HTTPException

from .api import register_api
from .auth import register_auth
from .errors import PanelError
from .manager import Registry
from .realtime import Realtime
from .storage import Store


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        DATA_DIR=os.environ.get("BEAMMPY_DATA_DIR", str(Path.cwd())),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("BEAMMPY_SECURE_COOKIES") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
        UPLOAD_LIMIT=int(os.environ.get("BEAMMPY_UPLOAD_LIMIT", 2 * 1024**3)),
        PUBLIC_ORIGIN=os.environ.get("BEAMMPY_PUBLIC_ORIGIN"),
        START_DELAY=0.35, STOP_TIMEOUT=15,
    )
    if config:
        app.config.update(config)
    data_dir = Path(app.config["DATA_DIR"]).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = portalocker.Lock(str(data_dir / ".panel.lock"), mode="a", timeout=0)
    try:
        lock.acquire()
    except portalocker.exceptions.LockException as exc:
        raise RuntimeError("Another BeamMPY process is using this data directory.") from exc
    try:
        if not app.config["SECRET_KEY"]:
            legacy = dotenv_values(data_dir / ".env")
            secret_path = data_dir / "panel.secret"
            if legacy.get("SECRET_KEY"):
                app.config["SECRET_KEY"] = legacy["SECRET_KEY"]
            else:
                if not secret_path.exists():
                    with secret_path.open("x", encoding="utf-8") as stream:
                        stream.write(secrets.token_urlsafe(48))
                    secret_path.chmod(0o600)
                app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8").strip()
        store = Store(data_dir / "users.db")
        store.import_legacy(data_dir / "server")
        socketio = SocketIO(app, async_mode="threading", transports=["polling"],
                            cors_allowed_origins=app.config["PUBLIC_ORIGIN"] or None,
                            logger=False, engineio_logger=False)
        realtime = Realtime(app, socketio)
        registry = Registry(store, data_dir, emit=realtime.publish,
                            command=app.config.get("PROCESS_COMMAND"), installer=app.config.get("INSTALLER"),
                            start_delay=app.config["START_DELAY"], stop_timeout=app.config["STOP_TIMEOUT"])
        app.extensions["store"] = store
        app.extensions["registry"] = registry
        register_auth(app, store, realtime.revoke)
        register_api(app, registry)
        realtime.register(registry)
        registry.reconcile()
    except BaseException:
        lock.release()
        raise

    closed = False

    def shutdown():
        nonlocal closed
        if closed:
            return
        closed = True
        try:
            registry.shutdown()
        finally:
            lock.release()
            atexit.unregister(shutdown)

    app.extensions["shutdown"] = shutdown
    atexit.register(shutdown)

    @app.errorhandler(PanelError)
    def panel_error(exc):
        return jsonify(error=str(exc)), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        # Avoid echoing configuration values/credentials from arbitrary exceptions.
        app.logger.error("Unhandled panel error: %s", type(exc).__name__)
        return jsonify(error="An unexpected panel error occurred. Check file permissions and retry."), 500

    @app.get("/dashboard")
    def old_dashboard():
        return redirect("/servers")

    @app.get("/register")
    def old_register():
        return redirect("/setup")

    @app.get("/")
    @app.get("/<path:path>")
    def frontend(path=""):
        if path == "api" or path.startswith(("api/", "socket.io/")):
            raise PanelError("Endpoint not found.", 404)
        web = Path(app.config.get("WEB_DIR", Path(__file__).parent / "web"))
        if path.startswith(("assets/", "licenses/")):
            return send_from_directory(web, path, max_age=31536000)
        if not (web / "index.html").exists():
            return "Frontend is not built. Run npm --prefix frontend ci, then npm --prefix frontend run build.", 503
        response = send_from_directory(web, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app
