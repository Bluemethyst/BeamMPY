import sys
from pathlib import Path
import time

import pytest

from beammpy import create_app


@pytest.fixture
def app(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "fake_server.py"
    application = create_app({"TESTING": True, "DATA_DIR": tmp_path, "SECRET_KEY": "test-only",
                              "PROCESS_COMMAND": lambda instance, executable: [sys.executable, "-u", str(fixture)],
                              "START_DELAY": 0.1, "STOP_TIMEOUT": 0.2,
                              "INSTALLER": fake_install})
    yield application
    application.extensions["shutdown"]()


def fake_install(directory, progress, cancelled):
    from beammpy.manager import find_executable
    import os
    name = "BeamMP-Server.exe" if os.name == "nt" else "BeamMP-Server.fixture"
    target = Path(directory) / name
    target.write_text("fixture executable marker", encoding="utf-8")
    target.chmod(0o700)
    progress(100, "Fixture installed")
    assert find_executable(directory)
    return "fixture-v1"


@pytest.fixture
def client(app):
    client = app.test_client()
    csrf = client.get("/api/auth/session").json["csrf_token"]
    result = client.post("/api/auth/setup", json={"username": "admin", "password": "test-password-123"},
                         headers={"X-CSRF-Token": csrf})
    assert result.status_code == 201
    return client


def headers(client):
    return {"X-CSRF-Token": client.get("/api/auth/session").json["csrf_token"]}


def wait_job(app, job_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        job = app.extensions["registry"].job(job_id)
        if job["state"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError("Operation did not finish")


def make_server(app, name="Test server", port=38001):
    registry = app.extensions["registry"]
    instance = registry.create(name, port, "test-auth-key")
    job = registry.operation(instance.id, "install")
    assert wait_job(app, job["id"])["state"] == "succeeded"
    return instance
