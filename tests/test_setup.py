"""Destructive installer operations must stay inside disposable managed paths."""
import json
from pathlib import Path
import sys

import pytest

from scripts import manage, setup


@pytest.fixture
def service_install(tmp_path, monkeypatch):
    root, data = tmp_path / 'program files', tmp_path / 'panel data'
    active = root / 'app' / 'environments' / 'fixture'
    manage.environment_python(active).parent.mkdir(parents=True)
    manage.environment_python(active).touch()
    data.mkdir()
    (data / 'users.db').write_bytes(b'unchanged account hashes')
    (data / 'ServerConfig.toml').write_text('# preserve configuration\n')
    (data / setup.MARKER).write_text('fixture-token')
    state = dict(format=setup.FORMAT, root=str(root), data_dir=str(data),
                 platform='ubuntu', account='fixture-user', data_token='fixture-token')
    setup.write_json(root / 'setup.json', state)
    setup.write_json(root / 'app' / 'installation.json', dict(active=str(active), data_dir=str(data)))
    unit = tmp_path / 'beammpy.service'
    unit.write_text(setup.service_header(root) + '[Service]\n')
    calls = []
    monkeypatch.setattr(setup, 'UNIT', unit)
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(setup.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(setup, 'systemctl', lambda *args: calls.append(args))
    monkeypatch.setattr(setup.subprocess, 'run', lambda *args, **kwargs: None)
    monkeypatch.setattr(manage, 'panel_check', lambda *args: None)
    return root, data, unit, calls


def test_uninstall_keeps_data_and_unexpected_files(service_install):
    root, data, unit, calls = service_install
    before = {p.name: p.read_bytes() for p in data.iterdir()}
    (root / 'owner-notes.txt').write_text('keep this too')
    setup.uninstall(root, False)
    assert calls[:2] == [('disable', '--now', 'beammpy.service'), ('daemon-reload',)]
    assert not unit.exists() and not (root / 'app').exists()
    assert {p.name: p.read_bytes() for p in data.iterdir()} == before
    assert (root / 'owner-notes.txt').read_text() == 'keep this too'


def test_purge_requires_exact_path_before_stopping_service(service_install, monkeypatch):
    root, data, unit, calls = service_install
    monkeypatch.setattr('builtins.input', lambda _: 'yes')
    with pytest.raises(ValueError, match='Confirmation'):
        setup.uninstall(root, True)
    assert unit.exists() and (root / 'app').exists() and data.exists() and calls == []
    monkeypatch.setattr('builtins.input', lambda _: str(data))
    setup.uninstall(root, True)
    assert not root.exists() and not data.exists() and not unit.exists()


@pytest.mark.parametrize('change', ['adopted-data', 'wrong-token', 'overlap', 'unrelated-service'])
def test_uninstall_rejects_changed_ownership_before_removing_anything(service_install, change):
    root, data, unit, calls = service_install
    state = json.loads((root / 'setup.json').read_text())
    if change == 'adopted-data':
        state.pop('data_token')
    elif change == 'wrong-token':
        (data / setup.MARKER).write_text('changed')
    elif change == 'overlap':
        state['data_dir'] = str(root / 'data')
    else:
        unit.write_text('[Service]\nExecStart=/another/program\n')
    setup.write_json(root / 'setup.json', state)
    with pytest.raises(ValueError):
        setup.uninstall(root, True)
    assert data.exists() and (root / 'app').exists() and unit.exists() and calls == []


def test_uninstall_refuses_a_manually_running_panel(service_install, monkeypatch):
    root, data, unit, calls = service_install
    def active(*args):
        raise ValueError('panel is active')
    monkeypatch.setattr(manage, 'panel_check', active)
    with pytest.raises(ValueError, match='panel is active'):
        setup.uninstall(root, False)
    assert (root / 'app').exists() and data.exists() and unit.exists()


def test_start_uses_saved_settings_and_allows_overrides(tmp_path, monkeypatch):
    active = tmp_path / 'environments' / 'fixture'
    manage.environment_python(active).parent.mkdir(parents=True)
    manage.environment_python(active).touch()
    setup.write_json(tmp_path / 'installation.json', dict(active=str(active), data_dir='private data', host='0.0.0.0', port=19254))
    calls = []
    monkeypatch.setattr(manage, 'run', lambda arguments: calls.append(list(map(str, arguments))))
    monkeypatch.setattr(sys, 'argv', ['manage.py', 'start', '--install-dir', str(tmp_path)])
    manage.main()
    assert calls[-1][-4:] == ['--host', '0.0.0.0', '--port', '19254']
    monkeypatch.setattr(sys, 'argv', ['manage.py', 'start', '--install-dir', str(tmp_path), '--host', '127.0.0.1', '--port', '19255'])
    manage.main()
    assert calls[-1][-4:] == ['--host', '127.0.0.1', '--port', '19255']
