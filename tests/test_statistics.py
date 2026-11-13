import json
import os
from pathlib import Path
import time

import psutil
import pytest

from beammpy import create_app
from beammpy.configuration import load_document
from beammpy.errors import PanelError
from beammpy.statistics import RETENTION, RECENT_RETENTION, Statistics
from beammpy.storage import Store
from conftest import headers, make_server, wait_job
from test_accounts import member


def start(app, instance):
    job = app.extensions["registry"].operation(instance.id, "start")
    assert wait_job(app, job["id"])["state"] == "succeeded"


def frame(stats, instance, **values):
    return "BEAMMPY_STATS:" + stats.plugins[instance.id]["token"] + ":" + json.dumps({
        "version": 1, "epoch": "first", "sequence": 1, "online": 2, "joins": 1, **values})


def test_statistics_permissions_and_session_revocation(app, client):
    one, two = make_server(app, "One", 39001), make_server(app, "Two", 39002)
    user, account = member(app, client, {one.id: ["statistics_view"], two.id: []})
    assert user.get(f"/api/servers/{one.id}/statistics").status_code == 200
    assert user.get(f"/api/servers/{two.id}/statistics").status_code == 403
    assert user.get("/api/servers/missing/statistics").status_code == 404
    assert user.get(f"/api/servers/{one.id}/statistics?range=forever").status_code == 400
    response = user.get(f"/api/servers/{one.id}/statistics")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json["server_id"] == one.id
    assert "directory" not in response.text and "token" not in response.text
    assert user.put(f"/api/servers/{one.id}/statistics/telemetry", json={"enabled": True}, headers=headers(user)).status_code == 403
    assert client.put(f"/api/servers/{one.id}/statistics/telemetry", json={"enabled": True}).status_code == 403
    socket = app.extensions["socketio"].test_client(app, flask_test_client=user, auth={"csrf_token": headers(user)["X-CSRF-Token"]})
    assert not socket.emit("subscribe", {"server_id": one.id}, callback=True)["ok"]
    assert client.put(f"/api/users/{account['id']}", json={"username": "member", "permissions": {one.id: []}}, headers=headers(client)).status_code == 200
    assert user.get(f"/api/servers/{one.id}/statistics").status_code == 401
    assert not socket.is_connected()
    user.post("/api/auth/login", json={"username": "member", "password": "member-password-123"}, headers=headers(user))
    assert user.get(f"/api/servers/{one.id}/statistics").status_code == 403


def test_only_owned_process_is_sampled_and_restart_resets_baseline(app, monkeypatch):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    start(app, instance)
    # Host-wide APIs must never contribute to a per-server value.
    monkeypatch.setattr(psutil, "cpu_percent", lambda *a, **k: pytest.fail("host CPU read"))
    monkeypatch.setattr(psutil, "virtual_memory", lambda: pytest.fail("host RAM read"))
    stats.collect()
    first = stats.snapshot(instance)["live"]
    assert first["status"] == "live" and first["cpu"] is None
    assert 0 < first["memory"] < 1000 and first["uptime"] >= 0
    stats.collect()
    assert stats.snapshot(instance)["live"]["cpu"] >= 0
    old = instance.process
    assert wait_job(app, app.extensions["registry"].operation(instance.id, "restart")["id"])["state"] == "succeeded"
    assert instance.process is not old
    assert stats.snapshot(instance)["live"]["status"] == "unavailable"
    stats.collect()
    assert stats.snapshot(instance)["live"]["cpu"] is None
    assert wait_job(app, app.extensions["registry"].operation(instance.id, "stop")["id"])["state"] == "succeeded"
    live = stats.snapshot(instance)["live"]
    assert live["status"] == "stopped" and live["cpu"] is None and live["memory"] is None


def test_wrong_process_identity_is_never_sampled(app):
    instance = make_server(app)
    start(app, instance)
    app.extensions["store"].update(instance.id, process_created=0)
    stats = app.extensions["statistics"]
    stats.collect()
    assert stats.snapshot(instance)["live"]["status"] == "unavailable"
    with stats.store.connection() as db:
        assert db.execute("SELECT count(*) FROM statistics_minutes").fetchone()[0] == 0
    # Restore the real identity for normal fixture shutdown.
    stats.store.update(instance.id, process_created=psutil.Process(instance.process.pid).create_time())


def test_minute_rollups_gaps_ranges_retention_and_cascade(app):
    one, two = make_server(app, "One", 39001), make_server(app, "Two", 39002)
    stats = app.extensions["statistics"]
    now = int(time.time()) // 300 * 300 + 120
    stats._record(one.id, now - 60, cpu=25, memory=100, players=2, joins=1)
    stats._record(one.id, now - 55, cpu=75, memory=200, players=5, joins=2)
    stats._record(two.id, now - 60, cpu=999, memory=999, players=100, joins=100)
    result = stats.snapshot(one, "1h", now)
    observed = [p for p in result["history"] if p["memory"] is not None]
    assert observed == [{"time": now - 60, "cpu": 50, "cpu_peak": 75, "memory": 150, "memory_peak": 200, "players": 5, "joins": 3}]
    assert result["summary"] == {"peak_players": 5, "joins": 3}
    assert any(p["cpu"] is None and p["players"] is None and p["joins"] is None for p in result["history"])
    for range_name in ("1h", "24h", "7d", "30d"):
        assert len(stats.snapshot(one, range_name, now)["history"]) <= 721
    stats._record(one.id, now - RETENTION - 120, cpu=500)
    stats.prune(now)
    with stats.store.connection() as db:
        assert db.execute("SELECT min(minute) FROM statistics_minutes").fetchone()[0] >= now - RETENTION
    app.extensions["registry"].delete(one.id, "One")
    with stats.store.connection() as db:
        assert db.execute("SELECT count(*) FROM statistics_minutes WHERE server_id=?", (one.id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM statistics_minutes WHERE server_id=?", (two.id,)).fetchone()[0] == 1


def test_history_persists_and_migration_preserves_accounts_grants(app, client):
    instance = make_server(app)
    _, account = member(app, client, {instance.id: ["maps"]})
    store = app.extensions["store"]
    with store.connection() as db:
        before = [tuple(row) for row in db.execute("SELECT * FROM users")]
        grants = [tuple(row) for row in db.execute("SELECT * FROM server_grants")]
        db.execute("DROP TABLE statistics_minutes")
        db.execute("DROP TABLE statistics_plugins")
        db.execute("PRAGMA user_version=3")
    reopened = Store(store.path)
    stats = Statistics(app.extensions["registry"])
    stats._record(instance.id, time.time(), cpu=30, memory=45)
    again = Statistics(app.extensions["registry"])
    assert any(p["memory"] == 45 for p in again.snapshot(instance)["history"])
    with reopened.connection() as db:
        assert [tuple(row) for row in db.execute("SELECT * FROM users")] == before
        assert [tuple(row) for row in db.execute("SELECT * FROM server_grants")] == grants
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5


def test_plugin_opt_in_preserves_config_and_requires_idle_admin(app, client):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    path = f"/api/servers/{instance.id}/statistics/telemetry"
    config = (instance.directory / "ServerConfig.toml").read_bytes()
    assert client.put(path, json={"enabled": "yes"}, headers=headers(client)).status_code == 400
    assert client.put(path, json={"enabled": True}, headers=headers(client)).status_code == 200
    target = instance.directory / "Resources/Server/BeamMPYStatistics/main.lua"
    assert target.is_file() and b"__TOKEN__" not in target.read_bytes()
    assert (instance.directory / "ServerConfig.toml").read_bytes() == config
    assert client.put(path, json={"enabled": True}, headers=headers(client)).status_code == 200
    start(app, instance)
    assert client.put(path, json={"enabled": False}, headers=headers(client)).status_code == 409
    assert wait_job(app, app.extensions["registry"].operation(instance.id, "stop")["id"])["state"] == "succeeded"
    instance.lock.acquire()
    try:
        assert client.put(path, json={"enabled": False}, headers=headers(client)).status_code == 409
    finally:
        instance.lock.release()
    assert client.put(path, json={"enabled": False}, headers=headers(client)).status_code == 200
    assert not target.exists()


@pytest.mark.parametrize("resource_kind", ["external", "shared", "overlap", "unknown"])
def test_plugin_rejects_non_private_resources(app, tmp_path, resource_kind):
    one, two = make_server(app, "One", 39001), make_server(app, "Two", 39002)
    from tomlkit import dumps
    if resource_kind == "external":
        document = load_document(one.directory)
        document["General"]["ResourceFolder"] = str(tmp_path / "external")
        (one.directory / "ServerConfig.toml").write_text(dumps(document), encoding="utf-8")
    else:
        document = load_document(two.directory)
        if resource_kind == "unknown":
            (two.directory / "ServerConfig.toml").write_text("invalid = [", encoding="utf-8")
        else:
            document["General"]["ResourceFolder"] = str(one.directory / "Resources" / ("nested" if resource_kind == "overlap" else ""))
            (two.directory / "ServerConfig.toml").write_text(dumps(document), encoding="utf-8")
    with pytest.raises(PanelError):
        app.extensions["statistics"].configure_plugin(one.id, True)
    assert not (one.directory / "Resources/Server/BeamMPYStatistics").exists()


def test_plugin_preserves_existing_changed_and_hardlinked_files(app):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    directory = instance.directory / "Resources/Server/BeamMPYStatistics"
    directory.mkdir()
    original = directory / "owner.lua"
    original.write_text("owner plugin", encoding="utf-8")
    with pytest.raises(PanelError):
        stats.configure_plugin(instance.id, True)
    assert original.read_text() == "owner plugin"
    original.unlink()
    directory.rmdir()
    stats.configure_plugin(instance.id, True)
    target = directory / "main.lua"
    content = target.read_bytes()
    target.write_bytes(content + b"\n-- changed")
    with pytest.raises(PanelError):
        stats.configure_plugin(instance.id, False)
    target.write_bytes(content)
    alias = instance.directory / "linked.lua"
    os.link(target, alias)
    with pytest.raises(PanelError):
        stats.configure_plugin(instance.id, False)
    assert target.exists() and alias.read_bytes() == content


def test_player_snapshots_are_aggregate_deduplicated_and_process_scoped(app):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    stats.configure_plugin(instance.id, True)
    start(app, instance)
    # Establish the real fixture's epoch before injecting a plugin reload. This
    # avoids racing a delayed process startup with deliberately synthetic frames.
    deadline = time.monotonic() + 5
    while instance.id not in stats.players and time.monotonic() < deadline:
        time.sleep(.01)
    assert instance.id in stats.players
    now, process = time.time(), instance.process
    assert not stats.ingest(instance, process, "ECHO " + frame(stats, instance))
    assert not stats.ingest(instance, object(), frame(stats, instance))
    assert stats.ingest(instance, process, frame(stats, instance), now)
    assert stats.ingest(instance, process, frame(stats, instance), now + 1)
    stats.ingest(instance, process, frame(stats, instance, sequence=2, online=0, joins=1), now + 2)
    stats.ingest(instance, process, frame(stats, instance, sequence=3, online=1, joins=2), now + 3)
    stats.ingest(instance, process, frame(stats, instance, sequence=2, online=99, joins=99), now + 4)
    result = stats.snapshot(instance, now=now + 4)
    assert result["summary"] == {"peak_players": 2, "joins": 2}
    assert result["live"]["players"] == 1
    assert stats.snapshot(instance, now=now + 30)["live"]["players"] is None
    # A plugin reload has a new epoch; old epoch frames cannot overwrite it.
    stats.ingest(instance, process, frame(stats, instance, epoch="second", sequence=1, online=3, joins=1), now + 5)
    stats.ingest(instance, process, frame(stats, instance, sequence=100, online=90, joins=100), now + 6)
    assert stats.snapshot(instance, now=now + 6)["summary"]["joins"] == 3
    assert stats.snapshot(instance, now=now + 6)["live"]["players"] == 3
    with stats.store.connection() as db:
        assert all(column[1] not in {"name", "ip", "player_id", "chat"} for column in db.execute("PRAGMA table_info(statistics_minutes)"))


@pytest.mark.parametrize("values", [{"online": -1}, {"online": True}, {"joins": "5"}, {"sequence": -1}, {"version": 2}, {"epoch": ""}, {"joins": 10**13}])
def test_malformed_player_telemetry_is_ignored(app, values):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    stats.configure_plugin(instance.id, True)
    process = object()
    instance.process = process
    try:
        assert stats.ingest(instance, process, frame(stats, instance, **values))
        assert instance.id not in stats.players
    finally:
        instance.process = None


def test_background_collector_runs_without_a_browser_and_shuts_down(tmp_path):
    from conftest import fake_install
    import sys
    app = create_app({"DATA_DIR": tmp_path, "SECRET_KEY": "statistics-test", "STATISTICS_INTERVAL": .05,
                      "PROCESS_COMMAND": lambda *a: [sys.executable, "-u", str(Path(__file__).parent / "fixtures/fake_server.py")],
                      "INSTALLER": fake_install, "START_DELAY": .1, "STOP_TIMEOUT": .2})
    stats = app.extensions["statistics"]
    try:
        instance = make_server(app)
        start(app, instance)
        deadline = time.monotonic() + 5
        while stats.snapshot(instance)["live"]["status"] != "live" and time.monotonic() < deadline:
            time.sleep(.05)
        assert stats.snapshot(instance)["live"]["memory"] > 0
    finally:
        app.extensions["shutdown"]()
    assert not stats.thread.is_alive()


def test_collection_continues_after_one_inaccessible_process(app, monkeypatch):
    one, two = make_server(app, "One", 39001), make_server(app, "Two", 39002)
    stats = app.extensions["statistics"]
    calls = []
    def sample(instance, now):
        calls.append(instance.id)
        if instance is one:
            raise psutil.AccessDenied()
    monkeypatch.setattr(stats, "sample", sample)
    stats.collect()
    assert calls == [one.id, two.id]


def test_collector_keeps_plugin_enabled_during_concurrent_creation(app, monkeypatch):
    make_server(app)
    stats = app.extensions["statistics"]
    created = []
    def create_while_sampling(*args):
        instance = app.extensions["registry"].create("Created while sampling", 39002, "fixture-key")
        stats.configure_plugin(instance.id, True)
        created.append(instance)
    monkeypatch.setattr(stats, "sample", create_while_sampling)
    stats.collect()
    assert created[0].id in stats.plugins


def test_exclusive_plugin_install_does_not_remove_a_concurrently_created_file(app, monkeypatch):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    original_open = Path.open
    def race(path, mode="r", *args, **kwargs):
        if path.name == "main.lua" and mode == "xb":
            with original_open(path, "wb") as stream:
                stream.write(b"externally-created-plugin")
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", race)
    with pytest.raises(FileExistsError):
        stats.configure_plugin(instance.id, True)
    assert (instance.directory / "Resources/Server/BeamMPYStatistics/main.lua").read_bytes() == b"externally-created-plugin"
    assert instance.id not in stats.plugins


def test_ten_second_history_is_distinct_persisted_and_keeps_long_rollups(app):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    now = int(time.time()) // 60 * 60 + 30
    stats._record(instance.id, now - 30, cpu=20, memory=100, players=1, joins=1)
    stats._record(instance.id, now - 20, cpu=80, memory=200, players=3, joins=2)
    restored = Statistics(app.extensions["registry"])
    recent = restored.snapshot(instance, "1h", now)
    points = [point for point in recent["history"] if point["memory"] is not None]
    assert recent["bucket_seconds"] == 10 and len(recent["history"]) == 361
    assert [point["time"] for point in points] == [now - 30, now - 20]
    assert [point["cpu"] for point in points] == [20, 80]
    assert [point["players"] for point in points] == [1, 3]
    assert recent["summary"] == {"joins": 3, "peak_players": 3}
    assert recent["history"][-1]["memory"] is None
    long = restored.snapshot(instance, "24h", now)
    observed = [point for point in long["history"] if point["memory"] is not None]
    assert len(observed) == 1 and observed[0]["cpu"] == 50 and observed[0]["cpu_peak"] == 80
    assert long["summary"]["joins"] == 3  # Never count both storage resolutions.


def test_detail_retention_and_deletion_leave_long_history_intact(app):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    now = int(time.time()) // 60 * 60
    stats._record(instance.id, now - RECENT_RETENTION - 60, cpu=25, memory=100)
    stats._record(instance.id, now, cpu=50, memory=200)
    stats.prune(now)
    with stats.store.connection() as db:
        assert db.execute("SELECT count(*) FROM statistics_recent").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM statistics_minutes").fetchone()[0] == 2
    app.extensions["registry"].delete(instance.id, instance.snapshot()["name"])
    with stats.store.connection() as db:
        assert db.execute("SELECT count(*) FROM statistics_recent").fetchone()[0] == 0


def test_schema_four_upgrade_preserves_existing_history_and_plugin(app):
    instance = make_server(app)
    stats = app.extensions["statistics"]
    stats.configure_plugin(instance.id, True)
    stats._record(instance.id, time.time(), cpu=25, memory=100, players=2, joins=4)
    with stats.store.connection() as db:
        before = [tuple(row) for row in db.execute("SELECT * FROM statistics_minutes")]
        plugins = [tuple(row) for row in db.execute("SELECT * FROM statistics_plugins")]
        db.execute("DROP TABLE statistics_recent")
        db.execute("PRAGMA user_version=4")
    migrated = Store(stats.store.path)
    with migrated.connection() as db:
        assert [tuple(row) for row in db.execute("SELECT * FROM statistics_minutes")] == before
        assert [tuple(row) for row in db.execute("SELECT * FROM statistics_plugins")] == plugins
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
    restored = Statistics(app.extensions["registry"])
    assert restored.snapshot(instance, "24h")["summary"]["joins"] == 4
    # Old minute rows cannot reconstruct ten-second observations.
    assert all(point["cpu"] is None for point in restored.snapshot(instance, "1h")["history"])
