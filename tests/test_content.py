import io
import json
import os
from pathlib import Path
import stat
import zipfile

import pytest

from beammpy import create_app
from beammpy.configuration import load_document, write_config
from beammpy.errors import PanelError
from beammpy.manager import Instance
from conftest import headers, make_server, wait_job


def zipped(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def server_zip(extra=None, prefix="My server/"):
    executable = "BeamMP-Server.exe" if os.name == "nt" else "BeamMP-Server.fixture"
    return zipped({prefix + "ServerConfig.toml": '[General]\nName="Archive name" # preserved\nPort=39001\nAuthKey="import-secret"\nResourceFolder="../outside"\n[Plugin]\nValue=42\n',
                   prefix + executable: b"fixture", **(extra or {})})


def send_mod(client, instance, content, filename="map.zip"):
    return client.post(f"/api/servers/{instance.id}/mods/upload", data={"file": (io.BytesIO(content), filename)},
                       headers=headers(client), content_type="multipart/form-data")


def test_creation_requires_and_preserves_authkey(app, client):
    for key in (None, "", "   ", 4, "a\nb"):
        result = client.post("/api/servers", json={"name": "Bad", "port": 39001, "auth_key": key}, headers=headers(client))
        assert result.status_code == 400
    assert app.extensions["registry"].all() == []
    result = client.post("/api/servers", json={"name": "Valid", "port": 39001, "auth_key": "creation-secret"}, headers=headers(client))
    assert result.status_code == 202
    assert "creation-secret" not in result.text
    instance = app.extensions["registry"].get(result.json["server"]["id"])
    assert load_document(instance.directory)["General"]["AuthKey"] == "creation-secret"
    assert wait_job(app, result.json["operation"]["id"])["state"] == "succeeded"
    write_config(instance.directory, {"AuthKey": ""})
    result = wait_job(app, app.extensions["registry"].operation(instance.id, "start")["id"])
    assert result["state"] == "failed" and "AuthKey" in result["message"]


def test_delete_confirmation_keep_files_and_permanent_delete(app, client):
    one = make_server(app, "One", 39001)
    two = make_server(app, "Two", 39002)
    assert client.delete(f"/api/servers/{one.id}", json={"confirmation": "wrong", "delete_files": True}, headers=headers(client)).status_code == 400
    assert one.directory.exists()
    assert client.delete(f"/api/servers/{one.id}", json={"confirmation": "One"}, headers=headers(client)).status_code == 200
    assert one.directory.exists()
    assert client.get(f"/api/servers/{one.id}").status_code == 404
    assert client.delete(f"/api/servers/{two.id}", json={"confirmation": "Two", "delete_files": True}, headers=headers(client)).status_code == 200
    assert not two.directory.exists()
    assert one.directory.exists()
    assert app.extensions["registry"].all() == []


def test_deleted_legacy_directory_is_not_reimported(tmp_path):
    legacy = tmp_path / "server"
    legacy.mkdir()
    write_config(legacy, {"Name": "Original", "AuthKey": "private"})
    config = {"TESTING": True, "DATA_DIR": tmp_path, "SECRET_KEY": "fixture"}
    app = create_app(config)
    row = app.extensions["registry"].all()[0]
    app.extensions["registry"].delete(row["id"], row["name"])
    app.extensions["shutdown"]()
    app = create_app(config)
    try:
        assert app.extensions["registry"].all() == []
        assert legacy.exists()
    finally:
        app.extensions["shutdown"]()


def test_delete_is_stopped_only_and_protects_data_root(app, client):
    instance = make_server(app)
    registry = app.extensions["registry"]
    assert wait_job(app, registry.operation(instance.id, "start")["id"])["state"] == "succeeded"
    assert client.delete(f"/api/servers/{instance.id}", json={"confirmation": instance.snapshot()["name"], "delete_files": True}, headers=headers(client)).status_code == 409
    assert instance.running()
    row = app.extensions["store"].add_server("Protected", app.config["DATA_DIR"])
    registry.instances[row["id"]] = Instance(registry, row)
    with pytest.raises(PanelError, match="protected"):
        registry.delete(row["id"], "Protected", True)
    assert (Path(app.config["DATA_DIR"]) / "users.db").is_file()


def test_delete_failure_retains_record(app, monkeypatch):
    instance = make_server(app)
    from beammpy import manager
    def failure(path): raise PermissionError("fixture")
    monkeypatch.setattr(manager.shutil, "rmtree", failure)
    with pytest.raises(PanelError, match="retained"):
        app.extensions["registry"].delete(instance.id, instance.snapshot()["name"], True)
    assert app.extensions["store"].server(instance.id)


def test_maps_and_mod_upload_toggle_isolation_and_current_map_guard(app, client):
    instance = make_server(app, "One", 39001)
    other = make_server(app, "Two", 39002)
    blob = zipped({"levels/my_trails/info.json": json.dumps({"title": "My Trails"}), "vehicles/car/body.json": "{}"})
    result = send_mod(client, instance, blob, "trails.zip")
    assert result.status_code == 201
    assert result.json["mods"][0]["enabled"] is True
    assert client.get(f"/api/servers/{other.id}/mods").json["mods"] == []
    maps = client.get(f"/api/servers/{instance.id}/maps").json["maps"]
    assert len([item for item in maps if item["kind"] == "stock"]) == 14
    assert any(item["name"] == "My Trails" and item["enabled"] for item in maps)
    path = "/levels/my_trails/info.json"
    assert client.put(f"/api/servers/{instance.id}/maps", json={"path": path}, headers=headers(client)).status_code == 200
    assert client.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trails.zip", "enabled": False}, headers=headers(client)).status_code == 409
    assert client.put(f"/api/servers/{instance.id}/maps", json={"path": "/levels/italy/info.json"}, headers=headers(client)).status_code == 200
    assert client.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trails.zip", "enabled": False}, headers=headers(client)).status_code == 200
    assert not (instance.directory / "Resources/Client/trails.zip").exists()
    assert (instance.directory / "Resources/.beammpy-disabled/trails.zip").read_bytes() == blob
    assert client.put(f"/api/servers/{instance.id}/maps", json={"path": path}, headers=headers(client)).status_code == 422
    assert client.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trails.zip", "enabled": True}, headers=headers(client)).status_code == 200
    assert (instance.directory / "Resources/Client/trails.zip").read_bytes() == blob
    assert send_mod(client, instance, blob, "TRAILS.zip").status_code == 409


def test_mod_changes_require_idle_instance(app, client):
    instance = make_server(app)
    registry = app.extensions["registry"]
    assert wait_job(app, registry.operation(instance.id, "start")["id"])["state"] == "succeeded"
    assert send_mod(client, instance, zipped({"vehicles/car/info.json": "{}"})).status_code == 409
    assert client.put(f"/api/servers/{instance.id}/maps", json={"path": "/levels/italy/info.json"}, headers=headers(client)).status_code == 409


@pytest.mark.parametrize("filename,content", [("../bad.zip", b"bad"), ("bad.zip", b"not a zip"),
                                            ("CON.zip", b"bad"), ("mod.zip", zipped({"../escape": "bad"}))])
def test_bad_mod_uploads_leave_no_files(app, client, filename, content):
    instance = make_server(app)
    assert send_mod(client, instance, content, filename).status_code in (400, 422)
    assert client.get(f"/api/servers/{instance.id}/mods").json["mods"] == []


def test_uploads_above_old_json_limit_and_configured_limit(app, client):
    instance = make_server(app)
    blob = zipped({"vehicles/car/large.bin": os.urandom(80 * 1024)})
    assert send_mod(client, instance, blob, "large.zip").status_code == 201
    app.extensions["content"].upload_limit = 100
    assert send_mod(client, instance, blob, "too-large.zip").status_code == 413
    assert [item["filename"] for item in client.get(f"/api/servers/{instance.id}/mods").json["mods"]] == ["large.zip"]


def test_server_zip_browser_upload_and_local_file_preserve_sources(app, client, tmp_path):
    blob = server_zip({"My server/Resources/Client/vehicle.zip": zipped({"vehicles/car/info.json": "{}"})})
    result = client.post("/api/servers/import", data={"name": "Browser import", "archive": (io.BytesIO(blob), "server.zip")}, headers=headers(client))
    assert result.status_code == 201
    assert "import-secret" not in result.text
    instance = app.extensions["registry"].get(result.json["server"]["id"])
    doc = load_document(instance.directory)
    assert doc["General"]["ResourceFolder"] == "Resources"
    assert doc["General"]["AuthKey"] == "import-secret"
    assert doc["Plugin"]["Value"] == 42
    assert "# preserved" in (instance.directory / "ServerConfig.toml").read_text(encoding="utf-8")
    assert instance.executable()
    assert len(client.get(f"/api/servers/{instance.id}/mods").json["mods"]) == 1
    original = tmp_path / "backup.zip"
    original.write_bytes(blob)
    result = client.post("/api/servers/import", json={"name": "Local archive", "directory": str(original)}, headers=headers(client))
    assert result.status_code == 201
    assert original.read_bytes() == blob


@pytest.mark.parametrize("badpath", ["../escape", "/absolute", "C:/outside", "nested/../../outside", "..\\outside"])
def test_unsafe_import_paths_are_rejected(app, client, badpath):
    blob = server_zip({badpath: "unsafe"})
    result = client.post("/api/servers/import", data={"name": "Bad", "archive": (io.BytesIO(blob), "bad.zip")}, headers=headers(client))
    assert result.status_code == 422
    assert app.extensions["registry"].all() == []
    assert list((Path(app.config["DATA_DIR"]) / "instances").iterdir()) == []


def test_zip_links_and_missing_executable_rejected(app, client):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        item = zipfile.ZipInfo("link")
        item.create_system = 3
        item.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(item, "../../outside")
    for blob in (stream.getvalue(), zipped({"ServerConfig.toml": "[General]\nPort=39001"})):
        result = client.post("/api/servers/import", data={"name": "Invalid", "archive": (io.BytesIO(blob), "bad.zip")}, headers=headers(client))
        assert result.status_code == 422
    assert app.extensions["registry"].all() == []


def test_relative_resource_folder_survives_archive_import(app):
    executable = "BeamMP-Server.exe" if os.name == "nt" else "BeamMP-Server.fixture"
    blob = zipped({"ServerConfig.toml": '[General]\nPort=39001\nResourceFolder="MyResources"\n', executable: b"fixture",
                   "MyResources/Client/car.zip": zipped({"vehicles/car/info.json": "{}"})})
    instance = app.extensions["content"].import_zip("Custom resources", io.BytesIO(blob))
    assert load_document(instance.directory)["General"]["ResourceFolder"] == "MyResources"
    assert app.extensions["content"].mods(instance)[0]["filename"] == "car.zip"


def test_version_one_database_upgrade_preserves_records(tmp_path):
    from beammpy.storage import Store
    store = Store(tmp_path / "users.db")
    row = store.add_server("Existing", tmp_path / "instance")
    with store.connection() as db:
        db.execute("DROP TABLE ignored_imports")
        db.execute("PRAGMA user_version=1")
        db.execute("INSERT INTO users(username,password) VALUES('legacy','unchanged-hash')")
    upgraded = Store(store.path)
    assert upgraded.server(row["id"])["name"] == "Existing"
    with upgraded.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT password FROM users").fetchone()[0] == "unchanged-hash"


def test_corrupt_compressed_mod_is_rejected(app, client):
    instance = make_server(app)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("vehicles/data.txt", "some mod content" * 100)
    raw = bytearray(stream.getvalue())
    name_size = int.from_bytes(raw[26:28], "little")
    extra_size = int.from_bytes(raw[28:30], "little")
    raw[30 + name_size + extra_size] = 7  # Invalid DEFLATE block type.
    assert send_mod(client, instance, bytes(raw), "corrupt.zip").status_code == 422
    assert app.extensions["content"].mods(instance) == []


def test_overlapping_instance_files_cannot_be_deleted(app):
    instance = make_server(app)
    nested = instance.directory / "nested"
    nested.mkdir()
    row = app.extensions["store"].add_server("Nested", nested)
    registry = app.extensions["registry"]
    registry.instances[row["id"]] = Instance(registry, row)
    with pytest.raises(PanelError, match="another instance"):
        registry.delete(instance.id, instance.snapshot()["name"], True)
    assert instance.executable().exists()
    assert nested.exists()


def test_delete_protects_resource_folder_shared_by_another_instance(app):
    one = make_server(app, "One", 39001)
    two = make_server(app, "Two", 39002)
    from beammpy.configuration import write_document
    doc = load_document(one.directory)
    doc["General"]["ResourceFolder"] = str(two.directory / "Resources")
    write_document(one.directory, doc)
    with pytest.raises(PanelError, match="another instance"):
        app.extensions["registry"].delete(two.id, "Two", True)
    assert two.directory.exists()


def test_server_backup_cannot_be_uploaded_as_a_client_mod(app, client):
    instance = make_server(app)
    response = send_mod(client, instance, server_zip(), "server-backup.zip")
    assert response.status_code == 422
    assert "Import server" in response.json["error"]
    assert app.extensions["content"].mods(instance) == []
