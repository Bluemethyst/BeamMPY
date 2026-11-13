import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import psutil
import pytest
import tomlkit

from beammpy.configuration import read_config
from beammpy.errors import PanelError
from beammpy.manager import Registry
from conftest import headers, make_server, wait_job


def operate(app, instance, action):
    return wait_job(app, app.extensions["registry"].operation(instance.id, action)["id"])


def eventually(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate()


def test_two_live_processes_commands_restart_and_history(app):
    one = make_server(app, "One", 38001)
    two = make_server(app, "Two", 38002)
    assert operate(app, one, "start")["state"] == "succeeded"
    assert operate(app, two, "start")["state"] == "succeeded"
    one.command_input("first")
    two.command_input("second")
    eventually(lambda: any(line["text"] == "ECHO first" for line in one.history))
    eventually(lambda: any(line["text"] == "ECHO second" for line in two.history))
    assert not any("second" in line["text"] for line in one.history)
    assert one.process.pid != two.process.pid
    old_pid = one.process.pid
    assert operate(app, one, "restart")["state"] == "succeeded"
    assert one.process.pid != old_pid
    assert two.running()
    assert operate(app, one, "stop")["state"] == "succeeded"
    assert one.state == "stopped" and not one.running()
    assert two.running()


def test_missing_executable_and_early_exit(app):
    instance = app.extensions["registry"].create("Missing", 38001, "test-auth-key")
    assert operate(app, instance, "start")["state"] == "failed"
    assert not instance.running()
    instance = make_server(app, "Early", 38002)
    (instance.directory / "early-exit").touch()
    assert operate(app, instance, "start")["state"] == "failed"
    eventually(lambda: instance.state == "error")
    assert any("READY" in line["text"] for line in instance.history)


def test_duplicate_start_and_operation_lock(app):
    instance = make_server(app)
    instance.lock.acquire()
    try:
        with pytest.raises(PanelError, match="already in progress"):
            app.extensions["registry"].operation(instance.id, "start")
    finally:
        instance.lock.release()
    assert operate(app, instance, "start")["state"] == "succeeded"
    with pytest.raises(PanelError, match="already running"):
        app.extensions["registry"].operation(instance.id, "start")
    with pytest.raises(PanelError, match="Stop the server"):
        app.extensions["registry"].save_config(instance.id, {"Name": "Changed"})
    with pytest.raises(PanelError, match="one command"):
        instance.command_input("say hello\nexit")


def test_occupied_port(app):
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        instance = make_server(app, port=port)
        assert operate(app, instance, "start")["state"] == "failed"
        assert "occupied" in instance.snapshot()["error"]


def test_shutdown_escalates_and_stops_children(app):
    instance = make_server(app)
    (instance.directory / "ignore-exit").touch()
    assert operate(app, instance, "start")["state"] == "succeeded"
    process = instance.process
    descendants = psutil.Process(process.pid).children(recursive=True)
    app.extensions["shutdown"]()
    assert process.poll() is not None
    assert not any(child.is_running() for child in descendants)
    assert any("timed out" in line["text"] for line in instance.history)


def test_unexpected_exit_and_history_bound(app):
    instance = make_server(app)
    assert operate(app, instance, "start")["state"] == "succeeded"
    instance.process.kill()
    eventually(lambda: instance.state == "error")
    for index in range(1005):
        instance.append(str(index))
    assert len(instance.history) == 1000
    assert instance.history[0]["text"] == "5"


def test_config_preserves_comments_plugin_values_and_secret(app, client, monkeypatch):
    instance = make_server(app)
    path = instance.directory / "ServerConfig.toml"
    original = '# owner comment\n[General]\nName="Before" # name comment\nPort=38001\nAuthKey="do-not-expose"\n\n[Plugin]\nAnything = 42 # plugin comment\n'
    path.write_text(original, encoding="utf-8")
    instance.refresh_secret()
    result = client.get(f"/api/servers/{instance.id}/config")
    assert result.json["config"]["has_auth_key"] is True
    assert "do-not-expose" not in result.text
    result = client.put(f"/api/servers/{instance.id}/config", json={"Name": "After"}, headers=headers(client))
    assert result.status_code == 200
    assert type(result.json["config"]["Port"]) is int
    content = path.read_text(encoding="utf-8")
    assert '# owner comment' in content and '# name comment' in content and '# plugin comment' in content
    assert tomlkit.parse(content)["Plugin"]["Anything"] == 42
    assert tomlkit.parse(content)["General"]["AuthKey"] == "do-not-expose"
    instance.append("key=do-not-expose")
    assert instance.history[-1]["text"] == "key=[REDACTED]"
    from beammpy import configuration
    def failure(*args):
        raise PermissionError("fixture")
    monkeypatch.setattr(configuration.os, "replace", failure)
    result = client.put(f"/api/servers/{instance.id}/config", json={"Name": "Failed"}, headers=headers(client))
    assert result.status_code == 422
    assert path.read_text(encoding="utf-8") == content
    assert not list(instance.directory.glob(".config-*"))


@pytest.mark.parametrize("value", [{"Port": True}, {"Port": 10}, {"Port": "38001"}, {"MaxPlayers": 0},
                                   {"Private": "false"}, {"IP": "invalid"}, {"Name": ""}, {"Unknown": 4}])
def test_config_validation(app, client, value):
    instance = make_server(app)
    assert client.put(f"/api/servers/{instance.id}/config", json=value, headers=headers(client)).status_code == 400


def test_port_conflicts_and_authkey_clear(app, client):
    one = make_server(app, "One", 38001)
    two = make_server(app, "Two", 38002)
    assert client.put(f"/api/servers/{two.id}/config", json={"Port": 38001}, headers=headers(client)).status_code == 409
    registry = app.extensions["registry"]
    registry.save_config(one.id, {"AuthKey": "secret"})
    registry.save_config(one.id, {"Description": "Unrelated"})
    assert read_config(one.directory)["has_auth_key"] is True
    registry.save_config(one.id, {"AuthKey": ""})
    assert read_config(one.directory)["has_auth_key"] is False


def test_reconcile_matches_identity_and_leaves_unrelated_process(app):
    instance = make_server(app)
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        identity = psutil.Process(process.pid)
        store = app.extensions["store"]
        store.update(instance.id, process_pid=process.pid, process_created=identity.create_time() + 10,
                     process_executable=identity.exe())
        app.extensions["registry"].reconcile()
        assert process.poll() is None
        store.update(instance.id, process_pid=process.pid, process_created=identity.create_time(),
                     process_executable=identity.exe())
        app.extensions["registry"].reconcile()
        process.wait(timeout=5)
        assert store.server(instance.id)["process_pid"] is None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_console_auth_isolation_replay_and_logout(app, client):
    socketio = app.extensions["socketio"]
    anonymous = socketio.test_client(app, auth={"csrf_token": "invalid"})
    assert not anonymous.is_connected()
    assert not socketio.test_client(app, flask_test_client=client, auth={"csrf_token": "invalid"}).is_connected()
    one = make_server(app, "One", 38001)
    two = make_server(app, "Two", 38002)
    first = socketio.test_client(app, flask_test_client=client, auth={"csrf_token": headers(client)["X-CSRF-Token"]})
    second = socketio.test_client(app, flask_test_client=client, auth={"csrf_token": headers(client)["X-CSRF-Token"]})
    one.append("before subscription")
    assert first.emit("subscribe", {"server_id": one.id}, callback=True)["ok"]
    assert second.emit("subscribe", {"server_id": two.id}, callback=True)["ok"]
    assert any(event["name"] == "terminal_history" and event["args"][0]["lines"][0]["text"] == "before subscription" for event in first.get_received())
    second.get_received()
    one.append("one only")
    assert any(event["name"] == "terminal_output" for event in first.get_received())
    assert not second.get_received()
    assert not first.emit("command", {"server_id": one.id, "text": "say hello"}, callback=True)["ok"]
    assert operate(app, one, "start")["state"] == "succeeded"
    assert first.emit("command", {"server_id": one.id, "text": "hello"}, callback=True)["ok"]
    eventually(lambda: any(line["text"] == "ECHO hello" for line in one.history))
    client.post("/api/auth/logout", json={}, headers=headers(client))
    assert not first.is_connected() and not second.is_connected()


def test_revoked_token_cannot_receive_output(app, client):
    instance = make_server(app)
    socketio = app.extensions["socketio"]
    connection = socketio.test_client(app, flask_test_client=client, auth={"csrf_token": headers(client)["X-CSRF-Token"]})
    connection.emit("subscribe", {"server_id": instance.id})
    with app.extensions["store"].connection() as db:
        db.execute("DELETE FROM auth_sessions")
    instance.append("private output")
    assert not connection.is_connected()


def test_console_exit_is_stopped_and_pending_operation_is_visible(app):
    instance = make_server(app)
    assert operate(app, instance, "start")["state"] == "succeeded"
    instance.command_input("exit")
    eventually(lambda: instance.state == "stopped")
    assert not instance.running()
    registry = app.extensions["registry"]
    original = registry.installer
    import threading
    release = threading.Event()
    def delayed(directory, progress, cancelled):
        release.wait(timeout=3)
        return "fixture-v2"
    registry.installer = delayed
    try:
        job = registry.operation(instance.id, "install")
        assert instance.snapshot()["operation"]["id"] == job["id"]
    finally:
        release.set()
        wait_job(app, job["id"])
        registry.installer = original


@pytest.mark.parametrize("content", ['General="not a table"', '[General\nPort=bad'])
def test_invalid_toml_does_not_break_instance_listing(app, client, content):
    instance = make_server(app)
    (instance.directory / "ServerConfig.toml").write_text(content, encoding="utf-8")
    instance.refresh_secret()
    assert client.get("/api/servers").status_code == 200
    assert client.get(f"/api/servers/{instance.id}/config").status_code == 422


def test_process_is_not_left_running_when_ownership_write_fails(app, monkeypatch):
    instance = make_server(app)
    store = app.extensions["store"]
    update = store.update
    def failing_update(server_id, **fields):
        if fields.get("process_pid"):
            raise PermissionError("fixture database failure")
        return update(server_id, **fields)
    monkeypatch.setattr(store, "update", failing_update)
    assert operate(app, instance, "start")["state"] == "failed"
    assert not instance.running()


def test_shutdown_attempts_every_instance_when_one_fails(app, monkeypatch):
    one = make_server(app, "One", 38001)
    two = make_server(app, "Two", 38002)
    assert operate(app, two, "start")["state"] == "succeeded"
    original = one._stop
    def fail(): raise PanelError("fixture failure")
    monkeypatch.setattr(one, "_stop", fail)
    try:
        with pytest.raises(RuntimeError, match="could not be stopped"):
            app.extensions["registry"].shutdown()
        assert not two.running()
    finally:
        monkeypatch.setattr(one, "_stop", original)
