"""Run real PowerShell/Python argument binding and downloaded IEX prompts."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile

import pytest


REPO = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell bootstrap')
SETUP = '''import sys
assert sys.argv[1] == 'windows', sys.argv
assert sys.argv[2] == '--source', sys.argv
print('SETUP_RAN', flush=True)
print('CHOSEN_ROOT=' + input('Installation directory: '), flush=True)
'''


@pytest.mark.parametrize('shell', ['powershell.exe', 'pwsh.exe'])
@pytest.mark.parametrize('mode', ['file', 'download'])
def test_default_python_launcher_runs_setup_and_reads_prompts(tmp_path, shell, mode):
    executable = shutil.which(shell)
    if not executable or not shutil.which('py'):
        pytest.skip('Requires PowerShell and the default py launcher')
    environment = {**os.environ}
    environment.pop('BEAMMPY_PYTHON', None)  # The explicit override masked this bug.
    code = (REPO / 'scripts/install.ps1').read_text(encoding='utf-8')
    scripts = tmp_path / 'source with spaces' / 'scripts'
    scripts.mkdir(parents=True)
    server = None
    thread = None
    if mode == 'file':
        (scripts / 'setup.py').write_text(SETUP, encoding='utf-8')
        (scripts / 'install.ps1').write_text(code, encoding='utf-8')
        command = ['-File', str(scripts / 'install.ps1')]
    else:
        with zipfile.ZipFile(tmp_path / 'source.zip', 'w') as archive:
            archive.writestr('BeamMPY-main/scripts/setup.py', SETUP)
        handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        code = code.replace('https://codeload.github.com/Bluemethyst/BeamMPY/zip/refs/heads/main', base + '/source.zip')
        (tmp_path / 'install.ps1').write_text(code, encoding='utf-8')
        command = ['-Command', f'iwr -useb {base}/install.ps1 | iex; Write-Output "PREFERENCE=$ErrorActionPreference"']
    try:
        result = subprocess.run([executable, '-NoProfile', '-ExecutionPolicy', 'Bypass', *command],
            input='C:\\Fixture root with spaces\n', text=True, capture_output=True,
            env=environment, cwd=tmp_path, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'SETUP_RAN' in result.stdout, result.stdout + result.stderr
        assert 'CHOSEN_ROOT=C:\\Fixture root with spaces' in result.stdout
        if mode == 'download':
            assert 'PREFERENCE=Continue' in result.stdout  # IEX must not change caller settings.
        assert '>>>' not in result.stdout + result.stderr
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
