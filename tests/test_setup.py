"""Destructive installer operations must stay inside disposable managed paths."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

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


@pytest.mark.parametrize(('load_state', 'active', 'stop'), [
    ('bad-setting', False, False), ('loaded', False, True), ('bad-setting', True, True),
])
def test_rerun_can_replace_an_inactive_rejected_unit(monkeypatch, load_state, active, stop):
    calls = []
    monkeypatch.setattr(setup.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout=load_state))
    monkeypatch.setattr(setup, 'systemctl', lambda *args: calls.append(args))
    setup.stop_service_for_update(active)
    assert calls == ([('stop', 'beammpy.service')] if stop else [])


def test_failed_unit_validation_keeps_installed_unit(tmp_path, monkeypatch):
    unit = tmp_path / 'installed.service'
    unit.write_text('preserve the existing unit')
    monkeypatch.setattr(setup, 'UNIT', unit)
    state = dict(data_dir='/var/lib/beammpy', account='fixture', group='fixture', host='127.0.0.1', port=8524)
    def reject(arguments):
        raise subprocess.CalledProcessError(1, arguments)
    monkeypatch.setattr(manage, 'run', reject)
    with pytest.raises(subprocess.CalledProcessError):
        setup.write_service_unit(tmp_path, state, '/usr/bin/python3')
    assert unit.read_text() == 'preserve the existing unit'
    assert not list(tmp_path.glob('.service-check-*'))


@pytest.mark.skipif(sys.platform != 'linux' or not shutil.which('systemd-analyze'),
                    reason='Requires the real Linux systemd unit parser')
@pytest.mark.parametrize('directory', ['panel-data', 'panel data % literal $ value'])
def test_generated_service_passes_real_systemd_parser(tmp_path, monkeypatch, directory):
    import grp
    import pwd
    data = tmp_path / directory
    data.mkdir()
    state = dict(data_dir=str(data), account=pwd.getpwuid(os.getuid()).pw_name,
                 group=grp.getgrgid(os.getgid()).gr_name, host='127.0.0.1', port=8524)
    unit = tmp_path / 'installed.service'
    monkeypatch.setattr(setup, 'UNIT', unit)
    setup.write_service_unit(tmp_path, state, sys.executable)
    assert unit.is_file()


def test_linux_wheel_build_does_not_write_to_downloaded_source(tmp_path, monkeypatch):
    source = tmp_path / 'download'
    package = source / 'beammpy'
    (package / 'web').mkdir(parents=True)
    (package / 'web/index.html').write_text('bundled UI')
    (package / '__init__.py').write_text('')
    for name in ('pyproject.toml', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        (source / name).write_text('fixture')
    (source / '.env').write_text('private fixture; never copy into a package')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(setup.venv.EnvBuilder, 'create', lambda self, target: Path(target).mkdir())
    def wheel_build(arguments):
        build_source = Path(arguments[-1])
        assert not (build_source / '.env').exists()
        (build_source / 'build').mkdir()
        (build_source / 'build/root-owned-output').write_text('generated by elevated build')
        destination = Path(arguments[arguments.index('--wheel-dir') + 1])
        destination.mkdir()
        (destination / 'beammpy-0.4.1-py3-none-any.whl').write_bytes(b'fixture wheel')
    monkeypatch.setattr(manage, 'run', wheel_build)
    with setup.built_wheel(source, None) as wheel:
        assert wheel.is_file()
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()} == before
