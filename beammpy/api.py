from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
import json

from .auth import json_body
from .configuration import read_config
from .content import Content
from .errors import PanelError
from .permissions import PERMISSIONS, require_admin, require_server


def register_api(app, registry):
    api = Blueprint("api", __name__, url_prefix="/api")
    content = Content(registry, app.config["UPLOAD_LIMIT"])
    app.extensions["content"] = content

    @api.before_request
    @login_required
    def authenticate():
        if current_user.must_change_password:
            raise PanelError("Change your temporary password before managing servers.", 403)

    def snapshot(instance):
        result = instance.snapshot()
        if not current_user.is_admin:
            result.pop("directory", None)
        return result

    def mod_write_access(server_id, permission):
        require_server(server_id, permission)
        if current_user.is_admin:
            return
        instance = registry.get(server_id)
        root = content.resource_dirs(instance)[0].parent
        # Grants are instance-scoped. Existing installations can deliberately
        # share or externalize resources; only the administrator may change
        # those files, preserving the existing administrator workflow.
        if not root.is_relative_to(instance.directory):
            raise PanelError("An administrator must manage shared or external resource folders.", 403)
        with registry.mutation_lock:
            for other in registry.instances.values():
                if other.id == server_id:
                    continue
                try:
                    other_roots = (other.directory, content.resource_dirs(other)[0].parent)
                except PanelError as exc:
                    raise PanelError("Resource ownership could not be verified. Ask the administrator to check the other server configurations.", 403) from exc
                if any(root.is_relative_to(path) or path.is_relative_to(root) for path in other_roots):
                    raise PanelError("An administrator must manage shared or external resource folders.", 403)

    def name(value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 250:
            raise PanelError("Server name must contain 1–250 characters.")
        return value.strip()

    @api.get("/servers")
    def servers():
        return jsonify(servers=[snapshot(instance) for instance in list(registry.instances.values())
                                if current_user.is_admin or instance.id in current_user.permissions])

    @api.post("/servers")
    def create():
        if not current_user.can("create_servers"):
            raise PanelError("You do not have permission to create servers.", 403)
        body = json_body()
        instance = registry.create(name(body.get("name")), body.get("port", 30814), body.get("auth_key"))
        if not current_user.is_admin:
            with registry.store.connection() as db:
                db.execute("INSERT INTO server_grants(user_id,server_id,permissions) VALUES(?,?,?)",
                           (current_user.id, instance.id, json.dumps(list(PERMISSIONS))))
        operation = registry.operation(instance.id, "install")
        return jsonify(server=snapshot(instance), operation=operation), 202

    @api.post("/servers/import")
    def import_server():
        require_admin()
        if request.mimetype == "multipart/form-data":
            request.max_content_length = current_app.config["UPLOAD_LIMIT"] + 1024 * 1024
            upload = request.files.get("archive")
            if not upload or not upload.filename or not upload.filename.lower().endswith(".zip"):
                raise PanelError("Upload a server ZIP archive.")
            instance = content.import_zip(name(request.form.get("name")), upload.stream)
        else:
            body = json_body()
            instance = content.import_local(name(body.get("name")), body.get("directory"))
        return jsonify(server=instance.snapshot()), 201

    @api.get("/servers/<server_id>")
    def server(server_id):
        require_server(server_id)
        return jsonify(server=snapshot(registry.get(server_id)))

    @api.delete("/servers/<server_id>")
    def delete_server(server_id):
        require_admin()
        body = json_body()
        registry.delete(server_id, body.get("confirmation"), body.get("delete_files", False))
        return jsonify(deleted=True)

    @api.post("/servers/<server_id>/<action>")
    def operate(server_id, action):
        require_server(server_id, "power")
        if action == "install":
            require_admin()
        return jsonify(operation=registry.operation(server_id, action)), 202

    @api.get("/servers/<server_id>/config")
    def config(server_id):
        require_server(server_id, "configure")
        return jsonify(config=read_config(registry.get(server_id).directory))

    @api.put("/servers/<server_id>/config")
    def save_config(server_id):
        require_server(server_id, "configure")
        if not current_user.is_admin and "Map" in json_body():
            require_server(server_id, "maps")
        return jsonify(config=registry.save_config(server_id, json_body()))

    @api.get("/servers/<server_id>/maps")
    def maps(server_id):
        require_server(server_id)
        return jsonify(content.maps(registry.get(server_id)))

    @api.put("/servers/<server_id>/maps")
    def select_map(server_id):
        require_server(server_id, "maps")
        return jsonify(content.select_map(server_id, json_body().get("path")))

    @api.get("/servers/<server_id>/mods")
    def mods(server_id):
        require_server(server_id)
        return jsonify(mods=content.mods(registry.get(server_id)))

    @api.post("/servers/<server_id>/mods/state")
    def toggle_mod(server_id):
        mod_write_access(server_id, "mods_toggle")
        body = json_body()
        return jsonify(mods=content.toggle_mod(server_id, body.get("filename"), body.get("enabled")))

    @api.post("/servers/<server_id>/mods/upload")
    def upload_mod(server_id):
        mod_write_access(server_id, "mods_upload")
        request.max_content_length = current_app.config["UPLOAD_LIMIT"] + 1024 * 1024
        upload = request.files.get("file")
        if not upload or not upload.filename:
            raise PanelError("Choose a mod ZIP to upload.")
        return jsonify(mods=content.upload_mod(server_id, upload.filename, upload.stream)), 201

    @api.get("/operations/<operation_id>")
    def operation(operation_id):
        job = registry.job(operation_id)
        require_server(job["server_id"])
        return jsonify(operation=job)

    app.register_blueprint(api)
