"""Install the built wheel in a clean environment and verify it without Node."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import venv
import zipfile


def main():
    wheel = Path(sys.argv[1]).resolve()
    with zipfile.ZipFile(wheel) as archive:
        assert all(Path(name).name not in {"users.db", ".env", "ServerConfig.toml", "BeamMP-Server.exe"}
                   for name in archive.namelist()), "Runtime data must never be packaged"
    with tempfile.TemporaryDirectory(prefix="beammpy-wheel-") as root:
        root = Path(root)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)],
                       cwd=root, check=True)
        code = """
from pathlib import Path
import re
import shutil
import beammpy
assert shutil.which('node') is None
assert 'site-packages' in str(Path(beammpy.__file__).resolve())
app = beammpy.create_app({'DATA_DIR': 'runtime', 'SECRET_KEY': 'wheel-test-only'})
try:
    client = app.test_client()
    assert client.get('/api/auth/session').json['setup_required']
    index = client.get('/')
    assert index.status_code == 200
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', index.text):
        assert client.get(asset).status_code == 200, asset
    assert client.get('/licenses/Google-Sans-Flex-OFL.txt').status_code == 200
    assert client.get('/licenses/Material-Symbols-Apache-2.0.txt').status_code == 200
    bootstrap = client.get('/api/auth/session').json
    session = client.post('/api/auth/setup', json={'username': 'package-admin', 'password': 'abcdefgh'},
                          headers={'X-CSRF-Token': bootstrap['csrf_token']})
    assert session.status_code == 201
    assert session.json['user']['is_admin']
    headers = {'X-CSRF-Token': session.json['csrf_token']}
    instance = app.extensions['registry'].create('Package smoke', 39001, 'package-test-key')
    assert len(client.get('/api/servers/' + instance.id + '/maps').json['maps']) == 14
    assert client.get('/api/servers/' + instance.id + '/mods').json['mods'] == []
    selected = client.put('/api/servers/' + instance.id + '/maps', json={'path': '/levels/italy/info.json'}, headers=headers)
    assert selected.status_code == 200
    assert selected.json['current'] == '/levels/italy/info.json'
    created = client.post('/api/users', json={'username': 'wheel-member', 'password': 'ijklmnop', 'permissions': {instance.id: []}}, headers=headers)
    assert created.status_code == 201
    member = app.test_client()
    token = member.get('/api/auth/session').json['csrf_token']
    login = member.post('/api/auth/login', json={'username': 'wheel-member', 'password': 'ijklmnop'}, headers={'X-CSRF-Token': token})
    assert login.json['user']['must_change_password']
    assert member.get('/api/servers').status_code == 403
    assert client.get('/api/users').status_code == 200
    removed = client.delete('/api/users/' + created.json['user']['id'], json={'confirmation': 'wheel-member'}, headers=headers)
    assert removed.status_code == 200 and removed.json['deleted']
    assert member.get('/api/servers').status_code == 401
    deleted = client.delete('/api/servers/' + instance.id, json={'confirmation': 'Package smoke', 'delete_files': True}, headers=headers)
    assert deleted.status_code == 200 and not instance.directory.exists()
finally:
    app.extensions['shutdown']()
print('Clean wheel install: bundled UI/assets/licenses, accounts/password options/deletion, auth, maps, mods, deletion and CLI verified without Node.')
"""
        runtime_environment = {**os.environ, "PATH": str(python.parent) + os.pathsep + sys.base_prefix}
        subprocess.run([str(python), "-I", "-c", code], cwd=root, env=runtime_environment, check=True)
        subprocess.run([str(python), "-I", "-m", "beammpy", "--help"], cwd=root, env=runtime_environment, check=True)


if __name__ == "__main__":
    main()
