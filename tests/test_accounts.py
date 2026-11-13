import pytest
from werkzeug.security import check_password_hash

from conftest import headers, make_server, wait_job
from test_content import send_mod, zipped


def member(app, admin, permissions=None, create=False):
    response = admin.post("/api/users", json={"username": "member", "password": "temporary-password-123",
                          "permissions": permissions or {}, "can_create_servers": create}, headers=headers(admin))
    assert response.status_code == 201, response.json
    client = app.test_client()
    login = client.post("/api/auth/login", json={"username": "member", "password": "temporary-password-123"}, headers=headers(client))
    assert login.json["user"]["must_change_password"]
    assert client.get("/api/servers").status_code == 403
    assert client.post("/api/auth/password", json={"current_password": "temporary-password-123", "new_password": "member-password-123"}, headers=headers(client)).status_code == 200
    assert client.get("/api/servers").status_code == 401
    assert client.post("/api/auth/login", json={"username": "member", "password": "member-password-123"}, headers=headers(client)).status_code == 200
    return client, response.json["user"]


def test_member_permissions_and_cross_server_isolation(app, client):
    one, two = make_server(app, "One", 39001), make_server(app, "Two", 39002)
    user, _ = member(app, client, {one.id: ["maps"]})
    assert [item["id"] for item in user.get("/api/servers").json["servers"]] == [one.id]
    assert "directory" not in user.get(f"/api/servers/{one.id}").json["server"]
    assert user.get(f"/api/servers/{two.id}").status_code == 404
    assert user.get(f"/api/servers/{two.id}/maps").status_code == 404
    assert user.put(f"/api/servers/{one.id}/maps", json={"path": "/levels/italy/info.json"}, headers=headers(user)).status_code == 200
    assert user.put(f"/api/servers/{one.id}/maps", json={"path": "/levels/utah/info.json"}).status_code == 403
    for path, method, body in [("start", "POST", {}), ("mods/state", "POST", {"filename": "absent.zip", "enabled": False}),
                               ("mods/upload", "POST", {}), ("config", "PUT", {"Name": "changed"})]:
        assert user.open(f"/api/servers/{one.id}/{path}", method=method, json=body, headers=headers(user)).status_code == 403
    assert user.get(f"/api/servers/{one.id}/config").status_code == 403
    assert user.get("/api/users").status_code == 403
    assert user.post("/api/servers/import", json={}, headers=headers(user)).status_code == 403
    assert user.post("/api/servers", json={}, headers=headers(user)).status_code == 403
    assert user.delete(f"/api/servers/{one.id}", json={"confirmation": "One"}, headers=headers(user)).status_code == 403


def test_creation_grants_only_the_new_server_and_is_not_administration(app, client):
    other = make_server(app)
    user, _ = member(app, client, create=True)
    response = user.post("/api/servers", json={"name": "Created", "port": 39002, "auth_key": "test-key"}, headers=headers(user))
    assert response.status_code == 202
    server_id = response.json["server"]["id"]
    assert wait_job(app, response.json["operation"]["id"])["state"] == "succeeded"
    assert user.get(f"/api/servers/{other.id}").status_code == 404
    assert user.get(f"/api/servers/{server_id}/config").status_code == 200
    assert user.post(f"/api/servers/{server_id}/install", json={}, headers=headers(user)).status_code == 403
    job = app.extensions["registry"].operation(other.id, "install")
    assert user.get("/api/operations/" + job["id"]).status_code == 404
    assert user.get("/api/operations/" + response.json["operation"]["id"]).status_code == 200


def test_config_permission_cannot_bypass_map_permission(app, client):
    one = make_server(app)
    user, _ = member(app, client, {one.id: ["configure"]})
    assert user.put(f"/api/servers/{one.id}/config", json={"Map": "/levels/utah/info.json"}, headers=headers(user)).status_code == 403
    assert user.put(f"/api/servers/{one.id}/config", json={"Description": "allowed"}, headers=headers(user)).status_code == 200


def test_console_view_commands_scope_and_immediate_access_revocation(app, client):
    one, two = make_server(app), make_server(app, "Two", 39002)
    user, account = member(app, client, {one.id: ["console_view"]})
    socket = app.extensions["socketio"].test_client(app, flask_test_client=user, auth={"csrf_token": headers(user)["X-CSRF-Token"]})
    assert socket.emit("subscribe", {"server_id": two.id}, callback=True)["ok"] is False
    assert socket.emit("subscribe", {"server_id": one.id}, callback=True)["ok"] is True
    assert socket.emit("command", {"server_id": one.id, "text": "exit"}, callback=True)["ok"] is False
    assert socket.emit("command", {"server_id": [one.id], "text": "exit"}, callback=True)["ok"] is False
    assert client.put("/api/users/" + account["id"], json={"username": "member", "permissions": {}}, headers=headers(client)).status_code == 200
    assert not socket.is_connected()
    assert user.get("/api/servers").status_code == 401


@pytest.mark.parametrize("action", ["password", "logout-all"])
def test_password_and_signout_all_revoke_other_http_and_console_sessions(app, client, action):
    server = make_server(app)
    other = app.test_client()
    assert other.post("/api/auth/login", json={"username": "admin", "password": "test-password-123"}, headers=headers(other)).status_code == 200
    socket = app.extensions["socketio"].test_client(app, flask_test_client=other, auth={"csrf_token": headers(other)["X-CSRF-Token"]})
    assert socket.emit("subscribe", {"server_id": server.id}, callback=True)["ok"]
    body = {"current_password": "test-password-123", "new_password": "new-password-123"} if action == "password" else {}
    response = client.post("/api/auth/" + action, json=body, headers=headers(client))
    assert response.status_code == 200 and response.json["user"] is None
    assert not socket.is_connected()
    assert other.get("/api/servers").status_code == 401
    assert client.get("/api/servers").status_code == 401


def test_disable_and_admin_reset_require_new_member_password(app, client):
    user, account = member(app, client)
    assert client.post(f"/api/users/{account['id']}/password", json={"password": "another-temporary-123"}, headers=headers(client)).status_code == 200
    assert user.get("/api/servers").status_code == 401
    response = user.post("/api/auth/login", json={"username": "member", "password": "another-temporary-123"}, headers=headers(user))
    assert response.json["user"]["must_change_password"]
    assert user.post("/api/servers", json={}, headers=headers(user)).status_code == 403
    assert client.put(f"/api/users/{account['id']}", json={"username": "member", "enabled": False}, headers=headers(client)).status_code == 200
    assert user.post("/api/auth/login", json={"username": "member", "password": "another-temporary-123"}, headers=headers(user)).status_code == 401


@pytest.mark.parametrize("body", [{"permissions": {"not-a-server": []}}, {"enabled": "yes"}, {"is_admin": True},
                                  {"permissions": {"x": ["admin"]}}, {"permissions": []}])
def test_invalid_grants_and_privilege_escalation_are_atomic(app, client, body):
    response = client.post("/api/users", json={"username": "bad", "password": "temporary-password-123", **body}, headers=headers(client))
    assert response.status_code in (400, 409)
    assert len(client.get("/api/users").json["users"]) == 1


def test_admin_cannot_be_disabled_or_reset_through_member_api(app, client):
    admin = client.get("/api/auth/session").json["user"]
    assert admin["is_admin"]
    assert client.put(f"/api/users/{admin['id']}", json={"username": "admin", "enabled": False}, headers=headers(client)).status_code == 403
    assert client.post(f"/api/users/{admin['id']}/password", json={"password": "new-password-123"}, headers=headers(client)).status_code == 403
    assert client.post("/api/auth/password", json={"current_password": "wrong", "new_password": "new-password-123"}, headers=headers(client)).status_code == 403
    with app.extensions["store"].connection() as db:
        assert check_password_hash(db.execute("SELECT password FROM users").fetchone()[0], "test-password-123")


def test_granted_power_and_console_commands_work_without_config_access(app, client):
    instance = make_server(app)
    user, _ = member(app, client, {instance.id: ["power", "console_view", "console_command"]})
    result = user.post(f"/api/servers/{instance.id}/start", json={}, headers=headers(user))
    assert result.status_code == 202
    assert wait_job(app, result.json["operation"]["id"])["state"] == "succeeded"
    socket = app.extensions["socketio"].test_client(app, flask_test_client=user, auth={"csrf_token": headers(user)["X-CSRF-Token"]})
    assert socket.emit("subscribe", {"server_id": instance.id}, callback=True)["ok"]
    assert socket.emit("command", {"server_id": instance.id, "text": "help"}, callback=True)["ok"]
    result = user.post(f"/api/servers/{instance.id}/restart", json={}, headers=headers(user))
    assert wait_job(app, result.json["operation"]["id"])["state"] == "succeeded"
    result = user.post(f"/api/servers/{instance.id}/stop", json={}, headers=headers(user))
    assert wait_job(app, result.json["operation"]["id"])["state"] == "succeeded"
    assert user.get(f"/api/servers/{instance.id}/config").status_code == 403
    socket.disconnect()


def test_upload_and_toggle_grants_are_independent_and_keep_map_guard(app, client):
    instance = make_server(app)
    user, account = member(app, client, {instance.id: ["mods_upload"]})
    blob = zipped({"levels/trail/info.json": "{}"})
    assert send_mod(user, instance, blob, "trail.zip").status_code == 201
    assert user.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trail.zip", "enabled": False}, headers=headers(user)).status_code == 403
    assert client.put(f"/api/servers/{instance.id}/maps", json={"path": "/levels/trail/info.json"}, headers=headers(client)).status_code == 200
    assert client.put(f"/api/users/{account['id']}", json={"username": "member", "permissions": {instance.id: ["mods_toggle"]}}, headers=headers(client)).status_code == 200
    user.post("/api/auth/login", json={"username": "member", "password": "member-password-123"}, headers=headers(user))
    assert send_mod(user, instance, blob, "other.zip").status_code == 403
    assert user.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trail.zip", "enabled": False}, headers=headers(user)).status_code == 409
    client.put(f"/api/servers/{instance.id}/maps", json={"path": "/levels/italy/info.json"}, headers=headers(client))
    assert user.post(f"/api/servers/{instance.id}/mods/state", json={"filename": "trail.zip", "enabled": False}, headers=headers(user)).status_code == 200


def test_multiple_legacy_accounts_preserve_ids_hashes_and_assign_one_admin(tmp_path):
    import sqlite3
    from beammpy.storage import Store
    path = tmp_path / "users.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)")
        db.executemany("INSERT INTO users VALUES(?,?,?)", [(7, "owner", "preserved-one"), (9, "old-member", "preserved-two")])
    for _ in range(2):
        store = Store(path)
        with store.connection() as db:
            assert [tuple(row) for row in db.execute("SELECT id,username,password,is_admin FROM users ORDER BY id")] == [
                (7, "owner", "preserved-one", 1), (9, "old-member", "preserved-two", 0)]
            assert db.execute("SELECT count(*) FROM server_grants").fetchone()[0] == 0


@pytest.mark.parametrize("external_source", [True, False])
def test_member_mod_changes_cannot_affect_shared_resources(app, client, external_source):
    from beammpy.configuration import load_document, write_document
    one, two = make_server(app), make_server(app, "Two", 39002)
    changed, target = (one, two) if external_source else (two, one)
    document = load_document(changed.directory)
    document["General"]["ResourceFolder"] = str(target.directory / "Resources")
    write_document(changed.directory, document)
    blob = zipped({"vehicles/car/info.json": "{}"})
    assert send_mod(client, one, blob, "shared.zip").status_code == 201
    user, _ = member(app, client, {one.id: ["mods_upload", "mods_toggle"]})
    assert send_mod(user, one, blob, "other.zip").status_code == 403
    assert user.post(f"/api/servers/{one.id}/mods/state", json={"filename": "shared.zip", "enabled": False}, headers=headers(user)).status_code == 403
    resource_file = target.directory / "Resources/Client/shared.zip"
    assert resource_file.read_bytes() == blob
    assert not (resource_file.parent / "other.zip").exists()
    # The owner can still deliberately manage existing shared installations.
    assert client.post(f"/api/servers/{one.id}/mods/state", json={"filename": "shared.zip", "enabled": False}, headers=headers(client)).status_code == 200


@pytest.mark.parametrize("temporary", [True, False])
def test_eight_character_member_passwords_can_be_temporary_or_fixed(app, client, temporary):
    created = client.post("/api/users", json={"username": "eight", "password": "abcdefgh", "temporary": temporary}, headers=headers(client))
    assert created.status_code == 201
    account = created.json["user"]
    assert account["must_change_password"] is temporary
    user = app.test_client()
    result = user.post("/api/auth/login", json={"username": "eight", "password": "abcdefgh"}, headers=headers(user))
    assert result.status_code == 200
    assert user.get("/api/servers").status_code == (403 if temporary else 200)
    # Reset can set or clear the requirement, including an existing forced reset.
    result = client.post(f"/api/users/{account['id']}/password", json={"password": "ijklmnop", "temporary": not temporary}, headers=headers(client))
    assert result.status_code == 200
    assert user.get("/api/servers").status_code == 401
    result = user.post("/api/auth/login", json={"username": "eight", "password": "ijklmnop"}, headers=headers(user))
    assert result.json["user"]["must_change_password"] is not temporary
    assert user.get("/api/servers").status_code == (200 if temporary else 403)


@pytest.mark.parametrize("value", ["false", 0, 1, None])
def test_temporary_password_flag_requires_a_boolean(app, client, value):
    response = client.post("/api/users", json={"username": "bad", "password": "abcdefgh", "temporary": value}, headers=headers(client))
    assert response.status_code == 400
    created = client.post("/api/users", json={"username": "valid", "password": "abcdefgh", "temporary": False}, headers=headers(client)).json["user"]
    assert client.post(f"/api/users/{created['id']}/password", json={"password": "ijklmnop", "temporary": value}, headers=headers(client)).status_code == 400
    with app.extensions["store"].connection() as db:
        row = db.execute("SELECT password,must_change_password FROM users WHERE id=?", (created["id"],)).fetchone()
        assert check_password_hash(row["password"], "abcdefgh")
        assert not row["must_change_password"]


@pytest.mark.parametrize("password,status", [("abcdefg", 400), ("abcdefgh", 201)])
def test_setup_and_own_password_change_use_eight_character_minimum(app, password, status):
    user = app.test_client()
    response = user.post("/api/auth/setup", json={"username": "owner", "password": password}, headers=headers(user))
    assert response.status_code == status
    if status == 201:
        assert user.post("/api/auth/password", json={"current_password": password, "new_password": "abcdefg"}, headers=headers(user)).status_code == 400
        assert user.post("/api/auth/password", json={"current_password": password, "new_password": "ijklmnop"}, headers=headers(user)).status_code == 200
        assert user.post("/api/auth/login", json={"username": "owner", "password": "ijklmnop"}, headers=headers(user)).status_code == 200


def test_member_deletion_is_confirmed_admin_only_and_keeps_servers(app, client):
    server = make_server(app)
    user, account = member(app, client, {server.id: ["console_view"]}, create=True)
    created = user.post("/api/servers", json={"name": "Member created", "port": 39002, "auth_key": "fixture-key"}, headers=headers(user)).json
    assert wait_job(app, created["operation"]["id"])["state"] == "succeeded"
    owned = app.extensions["registry"].get(created["server"]["id"])
    original = (owned.directory / "ServerConfig.toml").read_bytes()
    socket = app.extensions["socketio"].test_client(app, flask_test_client=user, auth={"csrf_token": headers(user)["X-CSRF-Token"]})
    assert socket.emit("subscribe", {"server_id": server.id}, callback=True)["ok"]
    endpoint = f"/api/users/{account['id']}"
    assert user.delete(endpoint, json={"confirmation": "member"}, headers=headers(user)).status_code == 403
    assert client.delete(endpoint, json={"confirmation": "member"}).status_code == 403
    assert client.delete(endpoint, json={"confirmation": "wrong"}, headers=headers(client)).status_code == 409
    assert socket.is_connected() and user.get("/api/servers").status_code == 200
    admin = client.get("/api/auth/session").json["user"]
    assert client.delete(f"/api/users/{admin['id']}", json={"confirmation": "admin"}, headers=headers(client)).status_code == 403
    assert client.delete(endpoint, json={"confirmation": "member"}, headers=headers(client)).status_code == 200
    assert not socket.is_connected()
    assert user.get("/api/servers").status_code == 401
    assert owned.directory.is_dir() and (owned.directory / "ServerConfig.toml").read_bytes() == original
    assert app.extensions["store"].server(owned.id)
    with app.extensions["store"].connection() as db:
        assert not db.execute("SELECT 1 FROM users WHERE id=?", (account["id"],)).fetchone()
        assert not db.execute("SELECT 1 FROM server_grants WHERE user_id=?", (account["id"],)).fetchone()
        assert not db.execute("SELECT 1 FROM auth_sessions WHERE user_id=?", (account["id"],)).fetchone()
    assert client.delete(endpoint, json={"confirmation": "member"}, headers=headers(client)).status_code == 404
