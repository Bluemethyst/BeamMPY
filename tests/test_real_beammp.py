"""Opt-in real-binary smoke test; never uses an existing instance's config/key."""
import os
from pathlib import Path
import shutil
import socket
import time
import uuid

import pytest

from beammpy.configuration import write_config
from conftest import wait_job


@pytest.mark.skipif(not os.environ.get("BEAMMPY_SMOKE_BINARY"), reason="Set BEAMMPY_SMOKE_BINARY to opt in to a disposable real BeamMP smoke test.")
def test_real_binary_power_console_restart(app):
    source = Path(os.environ["BEAMMPY_SMOKE_BINARY"]).resolve()
    assert source.is_file()
    registry = app.extensions["registry"]
    registry.command = lambda instance, executable: [str(executable)]
    registry.start_delay = 2
    registry.stop_timeout = 15
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    instance = registry.create("Disposable real BeamMP smoke", port, str(uuid.uuid4()))
    target = instance.directory / ("BeamMP-Server.exe" if os.name == "nt" else source.name)
    shutil.copy2(source, target)
    target.chmod(0o700)
    # A throwaway key and loopback/private binding prevent using real credentials
    # or exposing a test instance. A real public-server AuthKey is not required.
    write_config(instance.directory, {"IP": "127.0.0.1", "Private": True, "AuthKey": str(uuid.uuid4())})
    job = wait_job(app, registry.operation(instance.id, "start")["id"])
    if job["state"] != "succeeded":
        pytest.fail("Real BeamMP start failed: " + job["message"] + "\n" + "\n".join(line["text"] for line in instance.history))
    before = instance.sequence
    instance.command_input("help")
    deadline = time.monotonic() + 5
    def help_received():
        return any(line["sequence"] > before and "displays this help" in line["text"].lower() for line in instance.history)
    while time.monotonic() < deadline and not help_received():
        time.sleep(0.1)
    assert help_received(), "BeamMP did not return the console help response after a stdin command."
    # Real servers may take longer than fixture jobs when shutting down.
    def wait_real(job_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = registry.job(job_id)
            if result["state"] != "running": return result
            time.sleep(0.1)
        pytest.fail("Real BeamMP operation timed out")
    assert wait_real(registry.operation(instance.id, "restart")["id"])["state"] == "succeeded"
    assert wait_real(registry.operation(instance.id, "stop")["id"])["state"] == "succeeded"
    assert not instance.running()
