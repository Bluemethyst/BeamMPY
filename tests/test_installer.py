from pathlib import Path

import pytest
import requests

from beammpy.errors import PanelError
from beammpy import installer
from conftest import make_server, wait_job


class Response:
    def __init__(self, payload=None, chunks=None):
        self.payload = payload
        self.chunks = chunks or [b"binary"]
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def json(self): return self.payload
    def iter_content(self, size):
        for chunk in self.chunks:
            if isinstance(chunk, Exception): raise chunk
            yield chunk


class HTTP:
    def __init__(self, release, chunks=None):
        self.release = release
        self.chunks = chunks
    def get(self, url, **kwargs):
        return Response(self.release) if url == installer.RELEASE_URL else Response(chunks=self.chunks)


@pytest.fixture
def release(monkeypatch):
    monkeypatch.setattr(installer, "asset_name", lambda: "BeamMP-Server.exe")
    return {"tag_name": "v9", "assets": [{"name": "BeamMP-Server.exe", "size": 6,
            "browser_download_url": "https://github.com/BeamMP/BeamMP-Server/releases/download/v9/BeamMP-Server.exe"}]}


def test_platform_matching():
    assert installer.asset_name("Windows", machine="AMD64") == "BeamMP-Server.exe"
    assert installer.asset_name("Linux", "ubuntu", "24.04", "x86_64") == "BeamMP-Server.ubuntu.24.04.x86_64"
    assert installer.asset_name("Linux", "debian", "13.1", "aarch64") == "BeamMP-Server.debian.13.arm64"
    with pytest.raises(PanelError): installer.asset_name("Linux", "unsupported", "1", "x86_64")
    with pytest.raises(PanelError): installer.asset_name("Darwin", machine="arm64")


def test_atomic_download_and_no_overwrite(tmp_path, release):
    progress = []
    assert installer.install(tmp_path, lambda *args: progress.append(args), lambda: False, HTTP(release)) == "v9"
    assert (tmp_path / "BeamMP-Server.exe").read_bytes() == b"binary"
    assert progress[-1][0] == 100
    with pytest.raises(PanelError, match="not be overwritten"):
        installer.install(tmp_path, lambda *args: None, lambda: False, HTTP(release))


@pytest.mark.parametrize("chunks", [[b"bi", requests.ConnectionError()], [b"bad"]])
def test_interrupted_download_can_retry(tmp_path, release, chunks):
    with pytest.raises(PanelError):
        installer.install(tmp_path, lambda *args: None, lambda: False, HTTP(release, chunks))
    assert not list(tmp_path.iterdir())
    assert installer.install(tmp_path, lambda *args: None, lambda: False, HTTP(release)) == "v9"


def test_cancel_and_missing_asset(tmp_path, release):
    with pytest.raises(PanelError, match="cancelled"):
        installer.install(tmp_path, lambda *args: None, lambda: True, HTTP(release))
    assert not list(tmp_path.iterdir())
    with pytest.raises(PanelError, match="no BeamMP"):
        installer.install(tmp_path, lambda *args: None, lambda: False, HTTP({"assets": []}))


def test_background_install_failure_and_retry(app):
    registry = app.extensions["registry"]
    instance = registry.create("Retry", 38003, "test-auth-key")
    original = registry.installer
    def fail(*args): raise PanelError("fixture network failure")
    registry.installer = fail
    result = wait_job(app, registry.operation(instance.id, "install")["id"])
    assert result["state"] == "failed"
    assert instance.state == "error"
    registry.installer = original
    assert wait_job(app, registry.operation(instance.id, "install")["id"])["state"] == "succeeded"
    assert instance.state == "stopped"
