"""Real interactive setup checks on a disposable Windows/systemd CI host.

Windows exercises iwr | iex with downloaded installer/source fixtures, the default
Python launcher, and the batch launcher from another cwd.
Ubuntu requires root, refuses any pre-existing beammpy unit/account, and exercises
install.sh through a PTY (including /dev/tty prompts), service access and uninstall.
Every path/account belongs to this fixture. Never run against an existing install.
"""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
import uuid
import zipfile
from version import release_wheel

import psutil


REPO = Path(__file__).resolve().parents[1]
HTTP = build_opener(ProxyHandler({}), HTTPCookieProcessor())


@contextmanager
def installer_downloads(work, platform):
    """Serve the working source as GitHub would after publication.

    Only fixture URLs are substituted; execute the documented download command
    and its real archive extraction instead of bypassing them with a source path.
    """
    directory = work / 'downloads'
    directory.mkdir()
    with zipfile.ZipFile(directory / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        # Git's file list excludes runtime data, environments and build artifacts.
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=REPO)
        for name in names.decode('utf-8').split('\0'):
            if name and (REPO / name).is_file():
                archive.write(REPO / name, 'BeamMPY-main/' + name)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(directory)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    filename = 'install.ps1' if platform == 'windows' else 'install.sh'
    installer = (REPO / 'scripts' / filename).read_text(encoding='utf-8')
    installer = installer.replace('https://codeload.github.com/Bluemethyst/BeamMPY/zip/refs/heads/main', base + '/source.zip')
    (directory / filename).write_text(installer, encoding='utf-8', newline='\n')
    try:
        yield (f'iwr -useb {base}/install.ps1 | iex' if platform == 'windows'
               else f'curl -fsSL {base}/install.sh | sh')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(url, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-CSRF-Token'] = token
    with HTTP.open(Request(url, data=json.dumps(payload).encode() if payload else None, headers=headers), timeout=5) as response:
        return response.read()


def snapshot(data):
    return {str(p.relative_to(data)): p.read_bytes() for p in data.rglob('*')
            if p.is_file() and p.name != '.panel.lock'}


def seed(base):
    session = json.loads(request(base + '/api/auth/session'))
    assert session['setup_required']
    created = json.loads(request(base + '/api/auth/setup',
        {'username': 'setup-fixture-admin', 'password': 'fixture-password-123'}, session['csrf_token']))
    assert created['user']['is_admin']
    index = request(base + '/').decode()
    assert 'BeamMPY' in index
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', index):
        assert request(base + asset)
    assert not json.loads(request(base + '/api/auth/session'))['setup_required']


def check_existing(base):
    deadline = time.monotonic() + 30
    while True:
        try:
            request(base + '/api/auth/session')
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)
    session = json.loads(request(base + '/api/auth/session'))
    assert not session['setup_required']
    login = json.loads(request(base + '/api/auth/login',
        {'username': 'setup-fixture-admin', 'password': 'fixture-password-123'}, session['csrf_token']))
    assert login['user']['is_admin']


def run(arguments, answers=None, **kwargs):
    subprocess.run(list(map(str, arguments)), input=answers, text=True, check=True, **kwargs)


def terminal_run(arguments, answers):
    import pty
    import select
    pid, descriptor = pty.fork()
    if pid == 0:
        os.execvp(str(arguments[0]), list(map(str, arguments)))
    # Give input only after input() is reached; sudo/pip/venv cannot consume it.
    pending = iter(answers.splitlines())
    buffer = b''
    sent = 0
    try:
        while True:
            readable, _, _ = select.select([descriptor], [], [], 1)
            if readable:
                try:
                    output = os.read(descriptor, 8192)
                except OSError:
                    break
                if not output:
                    break
                sys.stdout.buffer.write(output)
                sys.stdout.buffer.flush()
                buffer += output
                if buffer.endswith(b']: ') and sent < len(answers.splitlines()):
                    os.write(descriptor, (next(pending) + '\n').encode())
                    buffer = b''
                    sent += 1
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                assert os.waitstatus_to_exitcode(status) == 0
                return
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
    finally:
        os.close(descriptor)


def start_windows(root, cwd, base):
    log = open(cwd / 'batch-launch.log', 'w', encoding='utf-8')
    process = subprocess.Popen(['cmd.exe', '/d', '/c', str(root / 'Start BeamMPY.bat')],
                               cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                request(base + '/api/auth/session')
                return process, log
            except OSError:
                if process.poll() is not None:
                    raise AssertionError((cwd / 'batch-launch.log').read_text())
                time.sleep(0.25)
        raise AssertionError('Batch launcher did not serve HTTP: ' + (cwd / 'batch-launch.log').read_text())
    except BaseException:
        stop_windows(process, log)
        raise


def stop_windows(process, log):
    # This automated subprocess has no interactive console. Terminate only its
    # fixture process tree; interactive Ctrl+C is a separate manual check.
    if process.poll() is None:
        descendants = psutil.Process(process.pid).children(recursive=True)
        for child in reversed(descendants):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(descendants, timeout=10)
        process.terminate()
        process.wait(timeout=10)
    log.close()


def main():
    wheel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else release_wheel()
    windows = os.name == 'nt'
    account = 'beammpy-fixture-' + uuid.uuid4().hex[:8]
    if not windows:
        import pwd
        assert os.geteuid() == 0 and Path('/run/systemd/system').is_dir(), 'Use root on a disposable systemd host'
        found = subprocess.run(['systemctl', 'cat', 'beammpy.service'], capture_output=True)
        assert found.returncode != 0, 'Refusing to touch a host with a BeamMPY service'
        try:
            pwd.getpwnam(account)
        except KeyError:
            pass
        else:
            raise ValueError('Refusing to reuse an existing fixture account')
    with tempfile.TemporaryDirectory(prefix='beammpy-setup-') as temporary:
        work = Path(temporary)
        work.chmod(0o755)
        root, external = work / 'Panel with spaces', work / 'external import'
        external.mkdir()
        (external / 'keep.txt').write_text('external owner files')
        data = root / 'data' if windows else work / 'private panel data'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        if windows:
            powershell = shutil.which('powershell.exe')
            system = Path(os.environ['SystemRoot'])
            launcher = shutil.which('py')
            environment = {**os.environ,
                'PATH': os.pathsep.join(map(str, [Path(sys.executable).parent, Path(sys.base_prefix),
                    Path(launcher).parent if launcher else Path(sys.base_prefix),
                    system, system / 'System32', system / 'System32/WindowsPowerShell/v1.0']))}
            environment.pop('BEAMMPY_PYTHON', None)
            assert not shutil.which('node', path=environment['PATH'])
            answers = f'{root}\nlocal\n{port}\nyes\n'
            with installer_downloads(work, 'windows') as command:
                run([powershell, '-NoProfile', '-Command', command], answers, env=environment, cwd=work)
            process, log = start_windows(root, work, base)
            try:
                seed(base)
                denied = subprocess.run([sys.executable, REPO / 'scripts/setup.py', 'windows', '--wheel', wheel],
                    input=f'{root}\n\n\nyes\n', text=True, capture_output=True)
                assert denied.returncode != 0 and 'panel is active' in denied.stderr
            finally:
                stop_windows(process, log)
        else:
            answers = f'{root}\n{data}\nlan\n{port}\n{account}\nyes\n'
            with installer_downloads(work, 'ubuntu') as command:
                terminal_run(['sh', '-c', command], answers)
            seed(base)
            run(['systemctl', 'is-active', '--quiet', 'beammpy.service'])
            run(['systemctl', 'is-enabled', '--quiet', 'beammpy.service'])
            assert subprocess.check_output(['systemctl', 'show', '-p', 'User', '--value', 'beammpy.service'], text=True).strip() == account
            # Test a non-loopback interface too when the host has one.
            for address in subprocess.check_output(['hostname', '-I'], text=True).split():
                if ':' not in address:
                    assert json.loads(request(f'http://{address}:{port}/api/auth/session'))['setup_required'] is False
                    break
            run(['systemctl', 'stop', 'beammpy.service'])
        (data / '.env').write_text('PRESERVE=fixture-only\n')
        server = data / 'instances' / 'preservation-fixture'
        server.mkdir(parents=True, exist_ok=True)
        (server / 'ServerConfig.toml').write_text('# preserve this TOML\n[General]\nName="Owner files"\n')
        before = snapshot(data)
        # Rerun the installed setup using an explicit wheel; avoid another source build.
        platform = 'windows' if windows else 'ubuntu'
        answers = f'{root}\n\n\n' + (f'{account}\n' if not windows else '') + 'yes\n'
        run([sys.executable, root / 'setup.py', platform, '--wheel', wheel], answers, cwd=work)
        if not windows:
            run(['systemctl', 'stop', 'beammpy.service'])
        assert snapshot(data) == before, 'Rerun changed accounts/configuration/server files'
        if windows:
            process, log = start_windows(root, work, base)
            try:
                check_existing(base)
            finally:
                stop_windows(process, log)
            # Simulate documented Windows removal while retaining data and imports.
            shutil.rmtree(root / 'app')
            (root / 'Start BeamMPY.bat').unlink()
            assert snapshot(data)['.env'] == before['.env']
        else:
            run(['systemctl', 'start', 'beammpy.service'])
            check_existing(base)
            run(['sh', root / 'uninstall.sh'])
            retained = snapshot(data)
            assert retained['users.db'] and retained['.env'] == before['.env']
            assert not root.exists() and not Path('/etc/systemd/system/beammpy.service').exists()
            assert subprocess.run(['systemctl', 'is-active', '--quiet', 'beammpy.service']).returncode != 0
            assert subprocess.run(['systemctl', 'is-enabled', '--quiet', 'beammpy.service'], capture_output=True).returncode != 0
            # Reinstall retained managed data, then check purge refusal/confirmation.
            run([sys.executable, REPO / 'scripts/setup.py', 'ubuntu', '--wheel', wheel],
                f'{root}\n{data}\nlocal\n{port}\n{account}\nyes\n')
            rejected = subprocess.run(['sh', root / 'uninstall.sh', '--purge-data'], input='yes\n', text=True)
            assert rejected.returncode != 0 and data.exists()
            run(['sh', root / 'uninstall.sh', '--purge-data'], f'{data}\n')
            assert not root.exists() and not data.exists()
            assert subprocess.run(['id', account], capture_output=True).returncode == 0
            run(['userdel', account])  # This tool's unique disposable fixture only.
        assert (external / 'keep.txt').read_text() == 'external owner files'
    print(f'{sys.platform}: interactive installer, UI/setup, rerun preservation, launcher/service and removal checks passed.')


if __name__ == '__main__':
    main()
