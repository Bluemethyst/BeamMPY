import hmac
import threading

from flask import request, session
from flask_login import current_user
from flask_socketio import disconnect, emit, join_room, leave_room

from .errors import PanelError
from .permissions import require_server


class Realtime:
    def __init__(self, app, socketio):
        self.app = app
        self.socketio = socketio
        self.clients = {}
        self.lock = threading.RLock()

    def revoke(self, token):
        with self.lock:
            targets = [sid for sid, value in self.clients.items() if value == token]
            for sid in targets:
                self.socketio.server.disconnect(sid, namespace="/")
                self.clients.pop(sid, None)

    def publish(self, event, data):
        # Expired/revoked sessions must leave rooms before any further broadcast.
        with self.lock:
            for sid, token in list(self.clients.items()):
                if not self.app.extensions["valid_token"](token):
                    self.socketio.server.disconnect(sid, namespace="/")
                    self.clients.pop(sid, None)
            payload = {key: value for key, value in data.items() if key != "directory"}
            self.socketio.emit(event, payload, to="server:" + data["server_id"])

    def register(self, registry):
        socketio = self.socketio

        def authenticated():
            with self.lock:
                token = self.clients.get(request.sid)
            if not token or not self.app.extensions["valid_token"](token):
                disconnect()
                return False
            return True

        def authorize(server_id, permission):
            user = self.app.extensions["token_user"](self.clients.get(request.sid))
            if user is None:
                raise PanelError("Authentication required.", 401)
            require_server(server_id, permission, user)

        @socketio.on("connect")
        def connect(auth):
            csrf = auth.get("csrf_token", "") if isinstance(auth, dict) else ""
            if (not current_user.is_authenticated or not isinstance(csrf, str)
                    or not csrf or not hmac.compare_digest(csrf.encode(), session.get("csrf_token", "").encode())):
                return False
            with self.lock:
                self.clients[request.sid] = session["auth_token"]

        @socketio.on("disconnect")
        def disconnected(reason=None):
            with self.lock:
                self.clients.pop(request.sid, None)

        @socketio.on("subscribe")
        def subscribe(data):
            if not authenticated():
                return {"ok": False, "error": "Authentication required."}
            try:
                instance = registry.get(data.get("server_id") if isinstance(data, dict) else None)
                authorize(instance.id, "console_view")
                with instance.history_lock:
                    join_room("server:" + instance.id)
                    emit("terminal_history", {"server_id": instance.id, "lines": list(instance.history)})
                    snapshot = instance.snapshot()
                    snapshot.pop("directory", None)
                    emit("server_status", {"server_id": instance.id, **snapshot})
                return {"ok": True}
            except PanelError as exc:
                return {"ok": False, "error": str(exc)}

        @socketio.on("unsubscribe")
        def unsubscribe(data):
            if authenticated() and isinstance(data, dict) and isinstance(data.get("server_id"), str):
                leave_room("server:" + data["server_id"])

        @socketio.on("command")
        def command(data):
            if not authenticated():
                return {"ok": False, "error": "Authentication required."}
            try:
                if not isinstance(data, dict):
                    raise PanelError("Command must include a server ID and text.")
                authorize(data.get("server_id"), "console_command")
                registry.get(data.get("server_id")).command_input(data.get("text"))
                return {"ok": True}
            except PanelError as exc:
                return {"ok": False, "error": str(exc)}
