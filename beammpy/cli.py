import argparse
import getpass
import os
from pathlib import Path
import signal

import portalocker
from werkzeug.security import generate_password_hash

from . import create_app
from .storage import Store


def main():
    parser = argparse.ArgumentParser(description="BeamMPY server management panel")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    reset = sub.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    for command in (serve, reset):
        command.add_argument("--data-dir", default=os.environ.get("BEAMMPY_DATA_DIR", str(Path.cwd())))
    args = parser.parse_args()
    if args.command == "reset-password":
        data_dir = Path(args.data_dir).resolve()
        if not (data_dir / "users.db").is_file():
            parser.error("No existing users database in that data directory.")
        password = getpass.getpass("New password (12+ characters): ")
        if len(password) < 12 or len(password) > 1024 or password != getpass.getpass("Confirm password: "):
            parser.error("Passwords must match and contain 12–1024 characters.")
        # Reset is an offline maintenance operation; don't race a running panel.
        with portalocker.Lock(str(data_dir / ".panel.lock"), mode="a", timeout=0):
            store = Store(data_dir / "users.db")
            with store.connection() as db:
                row = db.execute("SELECT id FROM users WHERE username=?", (args.username,)).fetchone()
                if not row:
                    parser.error("Administrator account not found.")
                db.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(password), row["id"]))
                db.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["id"],))
        print("Password updated; existing sessions revoked.")
        return

    from waitress import create_server
    app = create_app({"DATA_DIR": args.data_dir})
    server = None
    previous = {}

    def stop(signum, frame):
        raise KeyboardInterrupt

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, stop)
        server = create_server(app, host=args.host, port=args.port, threads=32,
                               max_request_body_size=app.config["UPLOAD_LIMIT"] + 1024 * 1024)
        print(f"BeamMPY listening at http://{args.host}:{args.port}", flush=True)
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.close()
        app.extensions["shutdown"]()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
