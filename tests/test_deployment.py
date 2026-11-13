"""Installer failure and locking checks use private, disposable directories."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import portalocker
import pytest

from scripts import manage


def wheel(tmp_path):
    path = tmp_path / "beammpy-0.3.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("beammpy-0.3.0.dist-info/METADATA", "Name: beammpy\nVersion: 0.3.0\n")
    return path


def installation(tmp_path):
    root, data = tmp_path / "app", tmp_path / "data"
    active = root / "environments" / "existing"
    manage.environment_python(active).parent.mkdir(parents=True)
    manage.environment_python(active).touch()
    data.mkdir()
    (data / "users.db").write_bytes(b"preserve this database")
    (data / ".env").write_bytes(b"preserve credentials")
    state = {"active": str(active), "data_dir": str(data), "version": "old"}
    (root / "installation.json").write_text(json.dumps(state), encoding="utf-8")
    return root, data, state


def test_failed_install_preserves_previous_environment_manifest_and_data(tmp_path, monkeypatch):
    root, data, state = installation(tmp_path)
    originals = {path.name: path.read_bytes() for path in data.iterdir()}
    manifest = (root / "installation.json").read_bytes()
    monkeypatch.setattr(manage, "panel_check", lambda *args: None)
    def fail_build(self, target):
        target.mkdir()
        (target / "partial").touch()
        raise OSError("fixture disk failure")
    monkeypatch.setattr(manage.venv.EnvBuilder, "create", fail_build)
    args = argparse.Namespace(command="update", install_dir=str(root), wheel=str(wheel(tmp_path)), wheelhouse=None)
    with pytest.raises(OSError):
        manage.install(args)
    assert (root / "installation.json").read_bytes() == manifest
    assert list((root / "environments").iterdir()) == [Path(state["active"])]
    assert {path.name: path.read_bytes() for path in data.iterdir()} == originals
    assert not (root / ".install.lock").exists()


def test_activation_refuses_live_panel_and_keeps_previous_manifest(tmp_path):
    root, data, state = installation(tmp_path)
    staged = root / ".new.json"
    staged.write_text(json.dumps({**state, "version": "new"}), encoding="utf-8")
    with portalocker.Lock(str(data / ".panel.lock"), mode="a", timeout=0):
        with pytest.raises(ValueError, match="panel started"):
            manage.activate(root, staged)
        with pytest.raises(ValueError, match="panel is active"):
            manage.panel_check(Path(sys.executable), data)
    assert json.loads((root / "installation.json").read_text())["version"] == "old"
    assert staged.exists()
    manage.activate(root, staged)
    assert json.loads((root / "installation.json").read_text())["version"] == "new"


def test_install_rejects_overlapping_data_and_unmanaged_program_files(tmp_path):
    args = argparse.Namespace(command="install", install_dir=str(tmp_path / "app"), data_dir=str(tmp_path / "app/data"),
                              wheel=str(wheel(tmp_path)), wheelhouse=None)
    with pytest.raises(ValueError, match="separate"):
        manage.install(args)
    root = tmp_path / "app"
    root.mkdir()
    existing = root / "keep.txt"
    existing.write_text("keep")
    args.data_dir = str(tmp_path / "data")
    with pytest.raises(ValueError, match="not empty"):
        manage.install(args)
    assert existing.read_text() == "keep"


def test_another_installer_is_not_overridden(tmp_path):
    with manage.installation_lock(tmp_path):
        with pytest.raises(ValueError, match="installer"):
            with manage.installation_lock(tmp_path):
                pass
    assert not (tmp_path / ".install.lock").exists()


def test_failed_first_install_leaves_empty_program_directory_for_retry(tmp_path, monkeypatch):
    root = tmp_path / "app"
    def fail(self, target):
        target.mkdir()
        raise OSError("fixture venv failure")
    monkeypatch.setattr(manage.venv.EnvBuilder, "create", fail)
    args = argparse.Namespace(command="install", install_dir=str(root), data_dir=str(tmp_path / "data"),
                              wheel=str(wheel(tmp_path)), wheelhouse=None)
    with pytest.raises(OSError):
        manage.install(args)
    assert not list(root.iterdir())
