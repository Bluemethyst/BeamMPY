from pathlib import Path
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from beammpy import create_app
from beammpy.storage import Store
from conftest import headers, make_server


def test_legacy_migration_preserves_hash_and_files_and_is_idempotent(tmp_path):
    password_hash = generate_password_hash("existing-secret")
    database = tmp_path / "users.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT)")
        db.execute("INSERT INTO users VALUES(7,'existing',?)", (password_hash,))
    legacy = tmp_path / "server"
    legacy.mkdir()
    original = b'# Keep this comment\n[General]\nAuthKey="private-key"\n'
    (legacy / "ServerConfig.toml").write_bytes(original)
    settings = {"TESTING": True, "DATA_DIR": tmp_path, "SECRET_KEY": "fixture"}
    for _ in range(2):
        app = create_app(settings)
        try:
            store = app.extensions["store"]
            with store.connection() as db:
                assert db.execute("SELECT password FROM users WHERE id=7").fetchone()[0] == password_hash
                assert db.execute("PRAGMA user_version").fetchone()[0] == 5
            records = store.all_servers()
            assert len(records) == 1
            assert records[0]["directory"] == str(legacy.resolve())
            client = app.test_client()
            assert client.get("/api/auth/session").json["setup_required"] is False
            login = client.post("/api/auth/login", json={"username": "existing", "password": "existing-secret"},
                                headers=headers(client))
            assert login.status_code == 200
        finally:
            app.extensions["shutdown"]()
    assert (legacy / "ServerConfig.toml").read_bytes() == original


def test_singleton_lock(app):
    with pytest.raises(RuntimeError, match="Another BeamMPY"):
        create_app({"TESTING": True, "DATA_DIR": app.config["DATA_DIR"]})


def test_instances_are_isolated_and_persistent(app, client):
    one = make_server(app, "One", 38001)
    two = make_server(app, "Two", 38002)
    registry = app.extensions["registry"]
    registry.save_config(one.id, {"Description": "Only one"})
    assert one.directory != two.directory
    assert client.get(f"/api/servers/{one.id}/config").json["config"]["Description"] == "Only one"
    assert client.get(f"/api/servers/{two.id}/config").json["config"]["Description"] == ""
    records = Store(Path(app.config["DATA_DIR"]) / "users.db").all_servers()
    assert {row["id"] for row in records} == {one.id, two.id}
    assert all((Path(row["directory"]) / "Resources" / "Client").is_dir() for row in records)


def test_auth_setup_csrf_and_session_revocation(app, client):
    anonymous = app.test_client()
    assert anonymous.get("/api/servers").status_code == 401
    assert client.post("/api/servers", json={}).status_code == 403
    assert client.post("/api/servers", json={}, headers={"X-CSRF-Token": "\u2603"}).status_code == 403
    assert client.post("/api/auth/setup", json={"username": "another", "password": "other-password-123"},
                       headers=headers(client)).status_code == 409
    assert client.post("/api/auth/logout", json={}, headers=headers(client)).status_code == 200
    assert client.get("/api/servers").status_code == 401
    assert client.get("/api/unknown").status_code == 404


def test_import_does_not_modify_existing_directory(app, client, tmp_path):
    directory = tmp_path / "Imported server"
    directory.mkdir()
    from conftest import fake_install
    fake_install(directory, lambda *args: None, lambda: False)
    (directory / "ServerConfig.toml").write_text('# unchanged\n[General]\nPort=38010\n', encoding="utf-8")
    contents = {path.name: path.read_bytes() for path in directory.iterdir()}
    body = {"name": "Imported", "directory": str(directory)}
    assert client.post("/api/servers/import", json=body, headers=headers(client)).status_code == 201
    assert client.post("/api/servers/import", json=body, headers=headers(client)).status_code == 409
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == contents
    assert client.post("/api/servers/import", json={"name": "Bad", "directory": "relative"},
                       headers=headers(client)).status_code == 400
