import argparse
import getpass
import os
from pathlib import Path
import signal

import portalocker
from werkzeug.security import generate_password_hash

from . import create_app
from .storage import Store
from .auth import password_value
from .errors import PanelError


def main():
    parser = argparse.ArgumentParser(description="BeamMPY server management panel")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    reset = sub.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    setup = sub.add_parser("create-admin", help="Create the first administrator offline")
    setup.add_argument("--username", required=True)
    users = sub.add_parser("list-users", help="List account names for local recovery")
    for command in (serve, reset, setup, users):
        command.add_argument("--data-dir", default=os.environ.get("BEAMMPY_DATA_DIR", str(Path.cwd())))
    args = parser.parse_args()
    if args.command != "serve":
        data_dir = Path(args.data_dir).resolve()
        if args.command != "create-admin" and not (data_dir / "users.db").is_file():
            parser.error("No existing users database in that data directory.")
        if args.command == "create-admin":
            data_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Lock before prompting: an active panel must remain untouched.
            with portalocker.Lock(str(data_dir / ".panel.lock"), mode="a", timeout=0):
                store = Store(data_dir / "users.db")
                with store.connection() as db:
                    if args.command == "list-users":
                        for row in db.execute("SELECT username,is_admin,enabled FROM users ORDER BY id"):
                            print(f"{row['username']}  {'administrator' if row['is_admin'] else 'member'}  "
                                  f"{'enabled' if row['enabled'] else 'disabled'}")
                        return
                    username = args.username.strip()
                    if not 1 <= len(username) <= 80 or "\x00" in username:
                        parser.error("Username must contain 1–80 characters without null characters.")
                    if args.command == "create-admin":
                        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                            parser.error("Initial setup is already complete. Use reset-password for recovery.")
                    else:
                        row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                        if not row:
                            parser.error("Account not found. Use list-users to find the username.")
                    password = password_value(getpass.getpass("New password (8+ characters): "))
                    if password != getpass.getpass("Confirm password: "):
                        parser.error("Passwords do not match.")
                    if args.command == "create-admin":
                        db.execute("BEGIN IMMEDIATE")
                        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                            parser.error("Initial setup is already complete.")
                        db.execute("INSERT INTO users(username,password,is_admin) VALUES(?,?,1)",
                                   (username, generate_password_hash(password)))
                    else:
                        db.execute("UPDATE users SET password=?,must_change_password=0 WHERE id=?",
                                   (generate_password_hash(password), row["id"]))
                        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["id"],))
        except portalocker.exceptions.LockException:
            parser.error("Stop the panel before local account maintenance.")
        except PanelError as exc:
            parser.error(str(exc))
        print("Administrator created." if args.command == "create-admin" else "Password updated; existing sessions revoked.")
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
