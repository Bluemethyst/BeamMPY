"""Install a release wheel into a versioned venv; launch and recover locally.

Only the activation subprocess imports installed dependencies. This script can
bootstrap an installation with standard-library Python 3.11+ and no Node.
"""
import argparse
from contextlib import contextmanager
from email.parser import BytesParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv
import zipfile


def environment_python(environment):
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def load(root):
    path = root / "installation.json"
    if not path.is_file():
        raise ValueError("No managed installation here. Run install first with an explicit data directory.")
    state = json.loads(path.read_text(encoding="utf-8"))
    active = Path(state["active"]).resolve()
    if active.parent != (root / "environments").resolve() or not environment_python(active).is_file():
        raise ValueError("Invalid active environment; the installation was not changed.")
    return state


def run(arguments):
    subprocess.run([str(value) for value in arguments], check=True)


@contextmanager
def installation_lock(root):
    path = root / ".install.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Another installer may be active (.install.lock exists).") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink()


def wheel_version(wheel):
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("Choose a downloaded BeamMPY release wheel (.whl).")
    with zipfile.ZipFile(wheel) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Invalid wheel metadata.")
        package = BytesParser().parsebytes(archive.read(metadata[0]))
        if package["Name"].lower() != "beammpy":
            raise ValueError("The wheel must contain BeamMPY.")
        return package["Version"]


def panel_check(python, data_dir):
    # Use the same locking library and lock file as the panel, without opening
    # its database, reading secrets, or starting the application.
    result = subprocess.run([str(python), "-I", "-c", "import sys,portalocker; "
                             "lock=portalocker.Lock(sys.argv[1],mode='a',timeout=0); lock.acquire(); lock.release()",
                             str(data_dir / ".panel.lock")], capture_output=True)
    if result.returncode:
        raise ValueError("The panel is active or its data lock is unavailable. Stop it before updating.")


def activate(root, staged_path):
    import portalocker
    staged = Path(staged_path)
    state = json.loads(staged.read_text(encoding="utf-8"))
    # Recheck after installation and hold the panel's own lock until activation
    # is complete. A failed/rejected activation retains the previous manifest.
    try:
        with portalocker.Lock(str(Path(state["data_dir"]) / ".panel.lock"), mode="a", timeout=0):
            os.replace(staged, root / "installation.json")
    except portalocker.exceptions.LockException as exc:
        raise ValueError("The panel started during installation. Stop it and retry; the active environment was retained.") from exc


def install(args):
    root = Path(args.install_dir).expanduser().resolve()
    existing = load(root) if args.command == "update" else None
    data_dir = Path(existing["data_dir"] if existing else args.data_dir).expanduser().resolve()
    if root == data_dir or root.is_relative_to(data_dir) or data_dir.is_relative_to(root):
        raise ValueError("Program and data directories must be separate, with neither containing the other.")
    wheel = Path(args.wheel).expanduser().resolve()
    version = wheel_version(wheel)
    if not existing and root.exists() and any(root.iterdir()):
        raise ValueError("Install directory is not empty. Use update for a managed installation.")
    root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    with installation_lock(root):
        if existing:
            print("Checking that the panel is stopped...", flush=True)
            panel_check(environment_python(Path(existing["active"])), data_dir)
        target = root / "environments" / uuid.uuid4().hex
        target.parent.mkdir(exist_ok=True)
        staged = None
        activated = False
        new_launchers = []
        try:
            print(f"Installing BeamMPY {version} into a new private environment...", flush=True)
            venv.EnvBuilder(with_pip=True).create(target)
            python = environment_python(target)
            command = [python, "-I", "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:"]
            if args.wheelhouse:
                command.extend(["--no-index", "--find-links", str(Path(args.wheelhouse).resolve())])
            run([*command, wheel])
            run([python, "-I", "-m", "pip", "check"])
            # Validate in disposable data, never by opening the user's database.
            run([python, "-I", "-c", "import tempfile; from pathlib import Path; import beammpy; "
                 "assert (Path(beammpy.__file__).parent/'web'/'index.html').is_file(); "
                 "data=tempfile.TemporaryDirectory(prefix='beammpy-install-check-'); "
                 "app=beammpy.create_app({'DATA_DIR':data.name}); "
                 "assert app.test_client().get('/').status_code==200; "
                 "app.extensions['shutdown'](); data.cleanup()"])
            state = {"data_dir": str(data_dir), "active": str(target), "version": version,
                     "previous": existing["active"] if existing else None}
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                             prefix=".installation-", suffix=".json", delete=False) as stream:
                staged = Path(stream.name)
                json.dump(state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            # The installed manager remains usable independently of the source
            # checkout. Never put application files inside the runtime data dir.
            for name in ("manage.py", "beammpy.ps1", "beammpy.sh"):
                source = Path(__file__).parent / name
                destination = root / name
                if source.resolve() != destination.resolve():
                    if not destination.exists():
                        new_launchers.append(destination)
                    temporary = root / (".launcher-" + name)
                    shutil.copyfile(source, temporary)
                    os.replace(temporary, destination)
                if name.endswith(".sh"):
                    destination.chmod(0o700)
            run([python, "-I", str(Path(__file__).resolve()), "_activate", "--install-dir", root, str(staged)])
            activated = True
        finally:
            if staged and staged.exists():
                staged.unlink()
            # Remove only this newly allocated, verified environment on failure.
            # Existing installations and data are never recursively removed.
            if not activated and target.exists() and target.resolve().parent == (root / "environments").resolve() and not target.is_symlink():
                shutil.rmtree(target)
            if not activated:
                for path in new_launchers:
                    path.unlink(missing_ok=True)
                for name in ("manage.py", "beammpy.ps1", "beammpy.sh"):
                    (root / (".launcher-" + name)).unlink(missing_ok=True)
                try:
                    target.parent.rmdir()  # Empty staging parent only; keep existing environments.
                except OSError:
                    pass
        print(f"Installed BeamMPY {version}. Data directory: {data_dir}")
        print(f"Start from {root} using .\\beammpy.ps1 start (Windows) or ./beammpy.sh start (Linux).")
        print("Open http://127.0.0.1:8080 to create the administrator, or run create-admin --username YOUR_NAME.")
        if existing:
            print("The previous Python environment was retained. Back up data before first start; database migrations run on startup.")


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    parser = argparse.ArgumentParser(description="BeamMPY release installation and local maintenance")
    sub = parser.add_subparsers(dest="command", required=True)
    default_root = Path.home() / "BeamMPY" / "app"
    for name in ("install", "update"):
        command = sub.add_parser(name)
        command.add_argument("--install-dir", default=str(Path(__file__).resolve().parent
                             if name == "update" and (Path(__file__).parent / "installation.json").is_file() else default_root))
        command.add_argument("--wheel", required=True)
        command.add_argument("--wheelhouse", help="Offline dependency wheel directory")
        if name == "install":
            command.add_argument("--data-dir", default=str(Path.home() / "BeamMPY" / "data"))
    for name in ("start", "list-users", "reset-password", "create-admin"):
        command = sub.add_parser(name)
        command.add_argument("--install-dir", default=str(Path(__file__).resolve().parent))
        if name in ("reset-password", "create-admin"):
            command.add_argument("--username", required=True)
        if name == "start":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8080)
    worker = sub.add_parser("_activate", help=argparse.SUPPRESS)
    worker.add_argument("--install-dir", required=True)
    worker.add_argument("state")
    args = parser.parse_args()
    try:
        if args.command in ("install", "update"):
            install(args)
        elif args.command == "_activate":
            activate(Path(args.install_dir).resolve(), args.state)
        else:
            state = load(Path(args.install_dir).resolve())
            command = "serve" if args.command == "start" else args.command
            arguments = [environment_python(Path(state["active"])), "-I", "-m", "beammpy", command, "--data-dir", state["data_dir"]]
            if args.command == "start":
                arguments.extend(["--host", args.host, "--port", str(args.port)])
            elif args.command != "list-users":
                arguments.extend(["--username", args.username])
            run(arguments)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"BeamMPY maintenance failed ({type(exc).__name__}). Check paths, wheel compatibility and permissions; stop the panel before updating.\n"
                       + (str(exc) + "\n" if isinstance(exc, ValueError) else ""))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
