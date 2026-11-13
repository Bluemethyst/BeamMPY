"""Small, explicit per-server permissions shared by HTTP and Socket.IO."""
import json

from flask_login import current_user

from .errors import PanelError

PERMISSIONS = ("power", "maps", "mods_toggle", "mods_upload", "configure", "console_view", "console_command", "statistics_view")


def require_admin():
    if not current_user.is_admin:
        raise PanelError("Administrator access required.", 403)


def require_server(server_id, permission=None, user=None):
    user = current_user if user is None else user
    if not isinstance(server_id, str):
        raise PanelError("Server not found.", 404)
    if user.must_change_password:
        raise PanelError("Change your temporary password before managing servers.", 403)
    if not user.is_admin and server_id not in user.permissions:
        raise PanelError("Server not found.", 404)
    if permission and not user.can(permission, server_id):
        raise PanelError("You do not have permission for this action.", 403)


def grants_for(db, user_id):
    return {row["server_id"]: json.loads(row["permissions"])
            for row in db.execute("SELECT server_id,permissions FROM server_grants WHERE user_id=?", (user_id,))}
