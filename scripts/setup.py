"""Interactive platform setup, reusing the release-wheel environment manager.

Only standard-library Python is needed. Source downloads include the compiled UI.
Run through install.sh/install.ps1, or supply --wheel for offline verification.
"""
import argparse
from contextlib import contextmanager
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from urllib.error import URLError
from urllib.request import urlopen
import uuid
import venv

try:
    from . import manage
except ImportError:  # Executed as a standalone downloaded/installed script.
    # Installed maintenance reuses the manager and launchers in app/. Source
    # execution finds manage.py beside this script through the normal sys.path.
    installed_scripts = Path(__file__).resolve().parent / 'app'
    if (installed_scripts / 'manage.py').is_file():
        sys.path.insert(0, str(installed_scripts))
    import manage


UNIT = Path('/etc/systemd/system/beammpy.service')
MARKER = '.beammpy-installer-data'
FORMAT = 'beammpy-setup-v1'


def prompt(label, default):
    answer = input(f'{label} [{default}]: ').strip()
    return answer or str(default)


def absolute_path(value):
    if any(ord(character) < 32 for character in str(value)):
        raise ValueError('Directory paths must not contain control characters.')
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink() or path.resolve() == Path(path.anchor):
        raise ValueError('Choose an absolute directory path, without a symlink or filesystem root.')
    # Reject symlink ancestors too, especially before uninstall/purge.
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Installation and data paths must not pass through symlinks.')
    return path.resolve()


def separate(program, data):
    if program == data or program.is_relative_to(data) or data.is_relative_to(program):
        raise ValueError('Program and data directories must be separate and must not contain one another.')


def write_json(path, value):
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def read_setup(root):
    state = json.loads((root / 'setup.json').read_text(encoding='utf-8'))
    if state.get('format') != FORMAT or absolute_path(state['root']) != root:
        raise ValueError('Invalid setup record; no files were removed.')
    data = absolute_path(state['data_dir'])
    separate(root / 'app', data)
    if state['platform'] == 'ubuntu':
        separate(root, data)
    return state


def service_header(root):
    return f'# Managed by BeamMPY installer: {root}\n'


def check_unit(root):
    if UNIT.is_symlink() or (UNIT.exists() and not UNIT.read_text(encoding='utf-8').startswith(service_header(root))):
        raise ValueError('An unrelated beammpy.service already exists; it was not changed.')
    if not UNIT.exists():
        result = subprocess.run(['systemctl', 'show', '--property=FragmentPath', '--value', 'beammpy.service'],
                                capture_output=True, text=True, check=False)
        if result.stdout.strip():
            raise ValueError('Another beammpy.service is loaded from a different location; it was not changed.')


def systemctl(*arguments):
    manage.run(['systemctl', *arguments])


def stop_service_for_update(active):
    result = subprocess.run(['systemctl', 'show', '--property=LoadState', '--value', 'beammpy.service'],
                            capture_output=True, text=True, check=True)
    # An inactive unit rejected by the parser cannot always be stopped. Replace
    # it after validation so a rerun can recover a failed first installation.
    if active or result.stdout.strip() != 'bad-setting':
        systemctl('stop', 'beammpy.service')


def systemd_quote(value, command=False):
    # systemd uses its own command parser, never a shell. Escape specifiers and
    # environment expansion as well as ordinary quoting characters.
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if command:
        escaped = escaped.replace('$', '$$')
    return '"' + escaped + '"'


def service_text(root, state, python):
    arguments = [python, '-I', '-m', 'beammpy', 'serve', '--data-dir', state['data_dir'],
                 '--host', state['host'], '--port', str(state['port'])]
    return service_header(root) + '\n'.join([
        '[Unit]', 'Description=BeamMPY panel', 'After=network.target', '',
        '[Service]', 'Type=simple', f'User={state["account"]}', f'Group={state["group"]}',
        # WorkingDirectory is a single literal path, not an ExecStart word list.
        # Outer quotes are retained by its parser and make the path non-absolute.
        'WorkingDirectory=' + str(state['data_dir']).replace('%', '%%'),
        'ExecStart=' + ' '.join(systemd_quote(value, command=True) for value in arguments),
        'Restart=on-failure', 'RestartSec=5', 'UMask=0077', 'NoNewPrivileges=true',
        'ProtectSystem=full',
        # The CLI stops children in sequence. Allow every owned server to finish.
        'TimeoutStopSec=infinity', 'KillMode=mixed', '',
        '[Install]', 'WantedBy=multi-user.target', '',
    ])


def write_service_unit(root, state, python):
    text = service_text(root, state, python)
    with tempfile.TemporaryDirectory(prefix='.service-check-', dir=root) as temporary:
        candidate = Path(temporary) / 'beammpy.service'
        candidate.write_text(text, encoding='utf-8')
        # Catch unit syntax errors before overwriting/enabling the installed unit.
        manage.run(['systemd-analyze', 'verify', str(candidate)])
    UNIT.write_text(text, encoding='utf-8')


def stage_package_source(source, destination):
    destination.mkdir()
    for name in ('pyproject.toml', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(source / name, destination / name)
    shutil.copytree(source / 'beammpy', destination / 'beammpy',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    return destination


@contextmanager
def built_wheel(source, wheel):
    if wheel:
        yield Path(wheel).resolve()
        return
    source = Path(source).resolve()
    if not (source / 'beammpy' / 'web' / 'index.html').is_file():
        raise ValueError('The source download is missing its compiled UI. Use the official source archive or a release wheel.')
    with tempfile.TemporaryDirectory(prefix='beammpy-build-') as temporary:
        work = Path(temporary)
        build_source = source
        if sys.platform == 'linux':
            # Elevated setuptools builds write egg-info/build files in the source
            # tree. Stage only package inputs in a root-owned temporary directory
            # so the login user's downloaded tree remains theirs to clean up.
            build_source = stage_package_source(source, work / 'source')
        venv.EnvBuilder(with_pip=True).create(work / 'builder')
        python = manage.environment_python(work / 'builder')
        print('Preparing BeamMPY with its bundled interface...', flush=True)
        manage.run([python, '-I', '-m', 'pip', 'wheel', '--quiet', '--disable-pip-version-check',
                    '--no-deps', '--wheel-dir', work / 'wheels', build_source])
        wheels = list((work / 'wheels').glob('beammpy-*.whl'))
        if len(wheels) != 1:
            raise ValueError('The source build did not produce one BeamMPY wheel.')
        yield wheels[0]


def access_urls(host, port):
    if host != '0.0.0.0':
        return [f'http://{host}:{port}']
    addresses = []
    if os.name != 'nt':
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, check=False)
        for value in result.stdout.split():
            address = ipaddress.ip_address(value)
            if address.version == 4 and not address.is_loopback and not address.is_link_local:
                addresses.append(f'http://{address}:{port}')
    return [f'http://127.0.0.1:{port}', *dict.fromkeys(addresses)]


def wait_for_panel(host, port):
    address = '127.0.0.1' if host == '0.0.0.0' else host
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urlopen(f'http://{address}:{port}/api/auth/session', timeout=1) as response:
                if response.status == 200 and 'setup_required' in json.load(response):
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)
    raise ValueError('Service did not serve the panel within 30 seconds. Check: journalctl -u beammpy -n 80 --no-pager')


def ensure_account(name):
    import grp
    import pwd
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', name):
        raise ValueError('Choose a simple lowercase Linux account name.')
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        manage.run(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir',
                    '/nonexistent', '--shell', '/usr/sbin/nologin', name])
        account = pwd.getpwnam(name)
    if account.pw_uid == 0:
        raise ValueError('The panel must run under an unprivileged account.')
    return account, grp.getgrgid(account.pw_gid).gr_name


def install(args):
    linux = args.platform == 'ubuntu'
    if linux:
        if sys.platform != 'linux' or os.geteuid() != 0 or not Path('/run/systemd/system').is_dir():
            raise ValueError('Ubuntu setup requires root and a running systemd. Use sh install.sh with sudo available.')
        os.umask(0o022)  # Root-owned program files must be readable by the service account.
        print('Ubuntu service installation. Python 3.11+ and python3-venv are required.')
    else:
        if os.name != 'nt':
            raise ValueError('Windows setup must run on Windows.')
        print('Windows installation: foreground launch on demand, no automatic startup.')
    default = '/opt/beammpy' if linux else str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BeamMPY')
    root = absolute_path(prompt('Installation directory', default))
    existing = read_setup(root) if (root / 'setup.json').is_file() else None
    if existing and existing['platform'] != args.platform:
        raise ValueError('The existing installation belongs to a different platform.')
    if not existing and root.exists() and any(root.iterdir()):
        raise ValueError('That directory is not empty and is not managed by this installer. Choose a new directory.')
    data = absolute_path(existing['data_dir'] if existing else
                         prompt('Panel data directory', '/var/lib/beammpy') if linux else root / 'data')
    separate(root / 'app', data)
    if linux:
        separate(root, data)
        check_unit(root)
    print(f'Program and private Python environment: {root / "app"}\nAccounts, settings and local servers: {data}')
    if existing:
        print('Reusing the recorded data directory. Back up data and imported server folders before updating.')
    print('Local access binds 127.0.0.1; only this computer (or an SSH tunnel/proxy) can connect.')
    print('LAN access binds 0.0.0.0; other devices can connect. Use a trusted LAN and create the administrator promptly.')
    mode = prompt('Access: local or lan', 'lan' if existing and existing['host'] == '0.0.0.0' else 'local').lower()
    if mode not in ('local', 'lan'):
        raise ValueError('Access must be local or lan.')
    host = '0.0.0.0' if mode == 'lan' else '127.0.0.1'
    port = int(prompt('Panel TCP port', existing['port'] if existing else 8524))
    if not 1024 <= port <= 65535:
        raise ValueError('Choose a port between 1024 and 65535.')
    account_name = prompt('Unprivileged service account', existing['account'] if existing else 'beammpy') if linux else None
    if existing and linux and account_name != existing['account']:
        raise ValueError('Reuse the existing service account to preserve data ownership.')
    if prompt('Install these settings? yes/no', 'yes').lower() != 'yes':
        print('Installation cancelled.')
        return
    # Build before stopping an existing service. Failed builds leave it running.
    with built_wheel(args.source, args.wheel) as wheel:
        root.mkdir(parents=True, exist_ok=True)
        with manage.installation_lock(root):
            state = existing or {'format': FORMAT, 'root': str(root), 'data_dir': str(data), 'platform': args.platform}
            state = {**state, 'host': host, 'port': port}
            if linux:
                account, group = ensure_account(account_name)
                state.update(account=account_name, group=group)
            new_data = not data.exists()
            data.mkdir(parents=True, exist_ok=True)
            if new_data:
                (data / MARKER).write_text(uuid.uuid4().hex, encoding='utf-8')
            if (data / MARKER).is_file():
                state['data_token'] = (data / MARKER).read_text(encoding='utf-8')
            if linux:
                # Do not recursively chown imported/pre-existing data. Reuse its
                # account or arrange access explicitly when adopting existing data.
                if new_data:
                    data.chmod(0o700)
                    os.chown(data, account.pw_uid, account.pw_gid)
                    os.chown(data / MARKER, account.pw_uid, account.pw_gid)
                # Activation runs as root but the panel lock must remain writable
                # by the service account. Never follow an existing lock symlink.
                lock = data / '.panel.lock'
                if lock.is_symlink():
                    raise ValueError('The panel lock must not be a symlink.')
                if not lock.exists():
                    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(descriptor)
                    os.chown(lock, account.pw_uid, account.pw_gid)
                manage.run(['runuser', '--user', account_name, '--', 'test', '-w', str(data)])
                manage.run(['runuser', '--user', account_name, '--', 'test', '-w', str(lock)])
                check_unit(root)
            # Record ownership early so an interrupted first install can be rerun.
            write_json(root / 'setup.json', state)
            was_active = linux and UNIT.exists() and subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'beammpy.service']).returncode == 0
            if linux and UNIT.exists():
                stop_service_for_update(was_active)
            try:
                program = root / 'app'
                update = (program / 'installation.json').is_file()
                manage.install(SimpleNamespace(command='update' if update else 'install',
                    install_dir=str(program), data_dir=str(data), wheel=str(wheel), wheelhouse=args.wheelhouse, quiet=True))
            except BaseException:
                if was_active:
                    systemctl('start', 'beammpy.service')
                raise
            installation = manage.load(program)
            installation.update(host=host, port=port)
            write_json(program / 'installation.json', installation)
            # Keep maintenance available after the download directory disappears.
            for name in ('setup.py',):
                source = Path(__file__).resolve().parent / name
                if source != root / name:
                    shutil.copyfile(source, root / name)
            python = manage.environment_python(Path(installation['active']))
            if linux:
                # The service account must traverse/read root-owned program files.
                root.chmod(0o755)
                manage.run(['runuser', '--user', account_name, '--', str(python), '-I', '-c', 'import beammpy'])
                write_service_unit(root, state, python)
                (root / 'uninstall.sh').write_text('#!/bin/sh\nset -eu\ncd -- "$(dirname -- "$0")"\nexec python3 ./setup.py uninstall --root "$PWD" "$@"\n', encoding='utf-8')
                systemctl('daemon-reload')
                systemctl('enable', 'beammpy.service')
                systemctl('start', 'beammpy.service')
                systemctl('is-enabled', '--quiet', 'beammpy.service')
                systemctl('is-active', '--quiet', 'beammpy.service')
                wait_for_panel(host, port)
            else:
                (root / 'Start BeamMPY.bat').write_text('@echo off\r\n"%~dp0app\\Start BeamMPY.bat" %*\r\n', encoding='utf-8', newline='')
    print('\nInstallation complete. Open:')
    for url in access_urls(host, port):
        print('  ' + url)
    if linux and host == '127.0.0.1':
        print(f'Headless access: ssh -L {port}:127.0.0.1:{port} YOUR_USER@SERVER_IP, then open the localhost URL on your device.')
    elif host == '0.0.0.0':
        print(f'From another device use the server LAN IP on port {port}; 0.0.0.0 is a bind address, not a browser URL.')
        print('Allow this port in your host/network firewall if needed; the installer does not change firewall rules.')
    print('On first access, create the administrator (password: at least eight characters). Existing accounts remain in place.')
    if linux:
        print('Service started and enabled at boot. Status: sudo systemctl status beammpy')
        print('Logs: sudo journalctl -u beammpy -f\nRestart: sudo systemctl restart beammpy')
        print(f'Uninstall (keep data): sudo sh "{root}/uninstall.sh"')
    else:
        print(f'Double-click "{root / "Start BeamMPY.bat"}" to start. Press Ctrl+C in its console to stop.')
        print(f'To uninstall, stop the panel, keep/copy "{data}" and any imported folders, then remove the installation directory.')


def uninstall(root, purge):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Run Ubuntu uninstall with sudo.')
    root = absolute_path(root)
    state = read_setup(root)
    if state['platform'] != 'ubuntu':
        raise ValueError('This uninstall command is for Ubuntu service installations.')
    data = absolute_path(state['data_dir'])
    check_unit(root)
    if purge:
        token = state.get('data_token')
        marker = data / MARKER
        if not token or marker.is_symlink() or not marker.is_file() or marker.read_text(encoding='utf-8') != token:
            raise ValueError('Data was not created by this installer, or its marker changed. Remove it manually if intended.')
        print(f'PERMANENTLY DELETE accounts, configuration and all files under {data}. Imported folders elsewhere are retained.')
        if input('Type the full data directory to confirm: ').strip() != str(data):
            raise ValueError('Confirmation did not match. Nothing was uninstalled.')
    with manage.installation_lock(root):
        if UNIT.exists():
            systemctl('disable', '--now', 'beammpy.service')
        program = absolute_path(root / 'app')
        if (program / 'installation.json').is_file():
            installation = manage.load(program)
            if absolute_path(installation['data_dir']) != data:
                raise ValueError('Data records disagree; no program files were removed.')
            manage.panel_check(manage.environment_python(Path(installation['active'])), data)
        if UNIT.exists():
            UNIT.unlink()
        systemctl('daemon-reload')
        subprocess.run(['systemctl', 'reset-failed', 'beammpy.service'], capture_output=True, check=False)
        if program.exists():
            shutil.rmtree(program)
        if purge:
            shutil.rmtree(data)
        for name in ('setup.py', 'manage.py', 'setup.json', 'uninstall.sh'):
            (root / name).unlink(missing_ok=True)
        shutil.rmtree(root / '__pycache__', ignore_errors=True)
    try:
        root.rmdir()  # Keep unexpected files rather than recursively removing them.
    except OSError:
        pass
    print(f'Uninstalled BeamMPY. Service account {state["account"]} retained.')
    print(f'Data {"removed" if purge else "retained"}: {data}. Imported folders elsewhere were retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='platform', required=True)
    for name in ('windows', 'ubuntu'):
        command = sub.add_parser(name)
        command.add_argument('--source', default=str(Path(__file__).resolve().parents[1]))
        command.add_argument('--wheel')
        command.add_argument('--wheelhouse')
    remove = sub.add_parser('uninstall')
    remove.add_argument('--root', required=True)
    remove.add_argument('--purge-data', action='store_true')
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise ValueError('Python 3.11+ is required.')
        if args.platform == 'uninstall':
            uninstall(args.root, args.purge_data)
        else:
            install(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'BeamMPY setup failed: {exc}\n')
    except (KeyboardInterrupt, EOFError):
        parser.exit(1, '\nSetup cancelled. Existing data retained.\n')


if __name__ == '__main__':
    main()
