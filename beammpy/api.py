from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from .auth import json_body
from .configuration import read_config
from .content import Content
from .errors import PanelError


def register_api(app, registry):
    api = Blueprint("api", __name__, url_prefix="/api")
    content = Content(registry, app.config["UPLOAD_LIMIT"])
    app.extensions["content"] = content

    @api.before_request
    @login_required
    def authenticate():
        pass

    def name(value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 250:
            raise PanelError("Server name must contain 1–250 characters.")
        return value.strip()

    @api.get("/servers")
    def servers():
        return jsonify(servers=registry.all())

    @api.post("/servers")
    def create():
        body = json_body()
        instance = registry.create(name(body.get("name")), body.get("port", 30814), body.get("auth_key"))
        operation = registry.operation(instance.id, "install")
        return jsonify(server=instance.snapshot(), operation=operation), 202

    @api.post("/servers/import")
    def import_server():
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
        return jsonify(server=registry.get(server_id).snapshot())

    @api.delete("/servers/<server_id>")
    def delete_server(server_id):
        body = json_body()
        registry.delete(server_id, body.get("confirmation"), body.get("delete_files", False))
        return jsonify(deleted=True)

    @api.post("/servers/<server_id>/<action>")
    def operate(server_id, action):
        return jsonify(operation=registry.operation(server_id, action)), 202

    @api.get("/servers/<server_id>/config")
    def config(server_id):
        return jsonify(config=read_config(registry.get(server_id).directory))

    @api.put("/servers/<server_id>/config")
    def save_config(server_id):
        return jsonify(config=registry.save_config(server_id, json_body()))

    @api.get("/servers/<server_id>/maps")
    def maps(server_id):
        return jsonify(content.maps(registry.get(server_id)))

    @api.put("/servers/<server_id>/maps")
    def select_map(server_id):
        return jsonify(content.select_map(server_id, json_body().get("path")))

    @api.get("/servers/<server_id>/mods")
    def mods(server_id):
        return jsonify(mods=content.mods(registry.get(server_id)))

    @api.post("/servers/<server_id>/mods/state")
    def toggle_mod(server_id):
        body = json_body()
        return jsonify(mods=content.toggle_mod(server_id, body.get("filename"), body.get("enabled")))

    @api.post("/servers/<server_id>/mods/upload")
    def upload_mod(server_id):
        request.max_content_length = current_app.config["UPLOAD_LIMIT"] + 1024 * 1024
        upload = request.files.get("file")
        if not upload or not upload.filename:
            raise PanelError("Choose a mod ZIP to upload.")
        return jsonify(mods=content.upload_mod(server_id, upload.filename, upload.stream)), 201

    @api.get("/operations/<operation_id>")
    def operation(operation_id):
        return jsonify(operation=registry.job(operation_id))

    app.register_blueprint(api)
