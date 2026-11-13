"""Opt-in real-binary smoke test; never uses an existing instance's config/key."""
import os
from pathlib import Path
import shutil
import socket
import struct
import time
import uuid

import pytest

from beammpy.configuration import write_config
from conftest import wait_job


def assert_version_handshake(host, port):
    """Exercise code C without sending a player token or contacting player auth."""
    version = b"VC2.8.1"
    def receive(connection, size):
        response = b""
        while len(response) < size:
            chunk = connection.recv(size - len(response))
            assert chunk, "BeamMP closed the socket before accepting the version handshake."
            response += chunk
        return response
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b"C" + struct.pack("<i", len(version)) + version)
        length = struct.unpack("<i", receive(connection, 4))[0]
        assert 0 < length <= 4096, "Invalid BeamMP packet length."
        response = receive(connection, length)
        assert response == b"A", response


def wait_for_beammp_startup(instance, after=0):
    # A live process/listening socket does not imply BeamMP accepts players.
    # Either startup summary ends its Main=Starting gate, including with a
    # throwaway AuthKey. Player authentication is deliberately not attempted.
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and instance.running():
        if any(line["sequence"] > after and ("ALL SYSTEMS STARTED" in line["text"] or "STARTUP NOT SUCCESSFUL" in line["text"]) for line in instance.history):
            return
        time.sleep(0.1)
    pytest.fail("BeamMP did not finish startup:\n" + "\n".join(line["text"] for line in instance.history))


@pytest.mark.skipif(not os.environ.get("BEAMMPY_SMOKE_BINARY"), reason="Set BEAMMPY_SMOKE_BINARY to opt in to a disposable real BeamMP smoke test.")
@pytest.mark.parametrize("bind_ip, client_ip", [("::ffff:127.0.0.1", "127.0.0.1"), ("::1", "::1")])
def test_real_binary_power_console_restart(app, bind_ip, client_ip):
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
    write_config(instance.directory, {"IP": bind_ip, "Private": True, "AuthKey": str(uuid.uuid4())})
    statistics = app.extensions["statistics"]
    statistics.configure_plugin(instance.id, True)
    job = wait_job(app, registry.operation(instance.id, "start")["id"])
    if job["state"] != "succeeded":
        pytest.fail("Real BeamMP start failed: " + job["message"] + "\n" + "\n".join(line["text"] for line in instance.history))
    try:
        wait_for_beammp_startup(instance)
        deadline = time.monotonic() + 15
        while statistics.snapshot(instance)["live"]["players"] is None and time.monotonic() < deadline:
            time.sleep(.1)
        assert statistics.snapshot(instance)["live"]["players"] == 0, "Real BeamMP did not emit the bundled plugin's aggregate telemetry."
        statistics.collect()
        assert statistics.snapshot(instance)["live"]["memory"] > 0
        assert_version_handshake(client_ip, port)
        family = socket.AF_INET6 if ":" in client_ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as udp:
            udp.settimeout(5)
            udp.sendto(b"P", (client_ip, port))
            assert udp.recv(16) == b"P", "BeamMP UDP ping failed."
    except (OSError, AssertionError) as exc:
        pytest.fail(f"Real BeamMP connection failed: {exc}\n" + "\n".join(line["text"] for line in instance.history))
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
    before_restart = instance.sequence
    assert wait_real(registry.operation(instance.id, "restart")["id"])["state"] == "succeeded"
    wait_for_beammp_startup(instance, before_restart)
    assert_version_handshake(client_ip, port)
    deadline = time.monotonic() + 15
    while statistics.snapshot(instance)["live"]["players"] is None and time.monotonic() < deadline:
        time.sleep(.1)
    assert statistics.snapshot(instance)["live"]["players"] == 0
    assert wait_real(registry.operation(instance.id, "stop")["id"])["state"] == "succeeded"
    assert not instance.running()
