"""Release metadata drift must fail before publication/build."""
import json
from pathlib import Path
import shutil

import pytest

from tools.version import current_version, verify

ROOT = Path(__file__).resolve().parents[1]
FILES = ['beammpy/version.json', 'beammpy/web/version.json', 'pyproject.toml', 'README.md',
         'docs/INSTALLATION.md', 'frontend/package.json', 'frontend/package-lock.json',
         'frontend/src/App.vue', '.github/workflows/checks.yml']


@pytest.fixture
def metadata(tmp_path):
    for name in FILES:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    return tmp_path


def test_repository_versions_agree():
    assert verify() == []


@pytest.mark.parametrize('name', FILES[1:])
def test_drift_is_detected(metadata, name):
    path = metadata / name
    text = path.read_text(encoding='utf-8')
    if name.endswith('App.vue'):
        text = text.replace('../../beammpy/version.json', '../package.json')
    elif name.endswith('checks.yml'):
        text += '\n# accidental versioned command: beammpy-9.9.9-py3-none-any.whl\n'
    else:
        text = text.replace(current_version(), '9.9.9')
    path.write_text(text, encoding='utf-8')
    assert verify(metadata)


def test_approved_manifest_sync_requires_ui_rebuild_and_updates_both_lock_entries(metadata):
    (metadata / 'beammpy/version.json').write_text('{"version":"0.5.0"}')
    assert verify(metadata)
    assert verify(metadata, sync=True, source_only=True) == []
    assert verify(metadata) == ['Bundled UI version is stale or missing: rebuild frontend']
    lock = json.loads((metadata / 'frontend/package-lock.json').read_text())
    assert lock['version'] == lock['packages']['']['version'] == '0.5.0'
    assert '**0.5.0**' in (metadata / 'README.md').read_text()
