from collections import deque
from contextlib import contextmanager
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import uuid

import psutil

from .configuration import default_config, load_document, read_config, require_auth_key, validate_config, write_config
from .errors import PanelError
from .installer import install


def find_executable(directory):
    directory = Path(directory)
    if platform.system() == "Windows":
        path = directory / "BeamMP-Server.exe"
        return path.resolve() if path.is_file() else None
    for path in sorted(directory.glob("BeamMP-Server*")):
        if path.is_file() and not path.name.endswith((".download", ".exe", ".bak", ".old")) and os.access(path, os.X_OK):
            return path.resolve()
    return None


def terminate_owned_tree(pid, created, executable, popen=None):
    """Escalate only after verifying the persisted identity, including descendants."""
    try:
        root = psutil.Process(pid)
        if (abs(root.create_time() - created) >= 0.01
                or os.path.normcase(root.exe()) != os.path.normcase(executable)):
            return
        targets = root.children(recursive=True) + [root]
        for target in targets:
            try:
                if target.pid == pid and popen is not None:
                    # On Windows use the handle acquired at launch, rather than
                    # requesting a new terminate handle with potentially different ACLs.
                    popen.terminate()
                else:
                    target.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(targets, timeout=5)
        for target in alive:
            try:
                if target.pid == pid and popen is not None:
                    popen.kill()
                else:
                    target.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=5)
        if alive:
            raise PanelError("A server process could not be stopped. Stop it manually before restarting.", 409)
    except psutil.NoSuchProcess:
        pass


class Instance:
    def __init__(self, registry, row):
        self.registry = registry
        self.id = row["id"]
        self.directory = Path(row["directory"])
        self.lock = threading.Lock()
        self.history_lock = threading.RLock()
        self.history = deque(maxlen=1000)
        self.sequence = 0
        self.process = None
        self.reader = None
        self.state = "error" if row["last_error"] else "stopped"
        self.secret = ""
        self.refresh_secret()

    def refresh_secret(self):
        try:
            general = load_document(self.directory).unwrap().get("General", {})
            self.secret = str(general.get("AuthKey", "")) if isinstance(general, dict) else ""
        except PanelError:
            self.secret = ""

    def redact(self, text):
        return str(text).replace(self.secret, "[REDACTED]") if self.secret else str(text)

    def running(self):
        return self.process is not None and self.process.poll() is None

    def snapshot(self):
        row = self.registry.store.server(self.id)
        if not row:
            raise PanelError("Server not found.", 404)
        try:
            settings = read_config(self.directory)
            port = settings["Port"]
        except PanelError:
            port = None
        with self.registry.jobs_lock:
            operation = next((dict(job) for job in self.registry.jobs.values()
                              if job["server_id"] == self.id and job["state"] == "running"), None)
        return {"id": self.id, "name": row["name"], "directory": str(self.directory),
                "version": row["version"], "state": self.state, "running": self.running(),
                "executable_exists": self.executable() is not None, "port": port,
                "operation": operation,
                "error": self.redact(row["last_error"]) if row["last_error"] else None}

    def executable(self):
        return find_executable(self.directory)

    def set_state(self, state, error=None):
        self.state = state
        self.registry.store.update(self.id, last_error=error)
        self.registry.emit("server_status", {"server_id": self.id, **self.snapshot()})

    def append(self, text):
        with self.history_lock:
            self.sequence += 1
            clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
            line = {"sequence": self.sequence, "text": self.redact(clean), "time": time.time()}
            self.history.append(line)
            self.registry.emit("terminal_output", {"server_id": self.id, **line})

    def _read(self, process):
        try:
            for line in iter(lambda: process.stdout.readline(16384), ""):
                self.append(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            process.stdout.close()
            code = process.wait()
            if process.stdin:
                process.stdin.close()
            if (self.process is process and not self.registry.closing.is_set()
                    and self.state not in ("stopping", "stopped")):
                self.registry.store.update(self.id, process_pid=None, process_created=None, process_executable=None)
                if code == 0 and self.state == "running":
                    self.set_state("stopped")
                else:
                    self.set_state("error", f"Server exited unexpectedly (code {code}).")
                self.append(f"[Panel] Process exited (code {code}).")

    def _start(self):
        if self.registry.closing.is_set():
            raise PanelError("Panel is shutting down.", 503)
        if self.running():
            raise PanelError("Server is already running.", 409)
        executable = self.executable()
        if not executable:
            raise PanelError("Server executable not found. Install or import a compatible server.", 422)
        if self.reader:
            self.reader.join(timeout=2)
        config = read_config(self.directory)
        if not config["has_auth_key"]:
            raise PanelError("Configure an AuthKey before starting this server.", 422)
        validate_config({key: value for key, value in config.items() if key != "has_auth_key"})
        legacy_wildcard = config["IP"] == "0.0.0.0"
        if legacy_wildcard:
            config["IP"] = "::"
        self.registry.check_ports(self.id, config)
        self.registry.probe_ports(config)
        if legacy_wildcard:
            # Only repair the old panel wildcard, while stopped and after the
            # replacement bind was checked. Preserve explicit interface binds.
            write_config(self.directory, {"IP": "::"})
            self.append("[Panel] Changed the legacy bind IP 0.0.0.0 to :: (IPv4 + IPv6) to fix BeamMP client identification.")
        elif ":" not in config["IP"]:
            self.append("[Panel] Warning: IPv4-only bind addresses can cause 'bad address cast' when joining BeamMP 3.9.x. Use ::1 for local-only access or an IPv4-mapped IPv6 address for a specific IPv4 interface.")
        self.refresh_secret()
        self.set_state("starting")
        # Avoid inherited BEAMMP_* overrides silently defeating per-instance TOML.
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("BEAMMP_")}
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(self.registry.command(self, executable), cwd=self.directory,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", bufsize=1,
                                   env=environment, **kwargs)
        self.process = process
        try:
            identity = psutil.Process(process.pid)
            self.registry.store.update(self.id, process_pid=process.pid,
                                       process_created=identity.create_time(), process_executable=identity.exe())
        except Exception as exc:
            # Never leave a child alive when ownership could not be persisted.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
            raise PanelError("Server ownership could not be recorded. Check database permissions and the executable.", 422) from exc
        self.reader = threading.Thread(target=self._read, args=(process,), daemon=True)
        self.reader.start()
        time.sleep(self.registry.start_delay)
        if process.poll() is not None:
            raise PanelError("Server exited during startup. Check the console and configuration.", 422)
        self.set_state("running")

    def _stop(self):
        if not self.running():
            self.registry.store.update(self.id, process_pid=None, process_created=None, process_executable=None)
            self.set_state("stopped")
            return
        self.set_state("stopping")
        process = self.process
        try:
            process.stdin.write("exit\n")
            process.stdin.flush()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=self.registry.stop_timeout)
        except subprocess.TimeoutExpired:
            self.append("[Panel] Graceful shutdown timed out; terminating the process.")
            row = self.registry.store.server(self.id)
            terminate_owned_tree(process.pid, row["process_created"], row["process_executable"], popen=process)
            process.wait(timeout=5)
        finally:
            if not self.running() and process.stdin:
                process.stdin.close()
        if self.reader:
            self.reader.join(timeout=2)
        self.process = None
        self.registry.store.update(self.id, process_pid=None, process_created=None, process_executable=None)
        self.set_state("stopped")

    def command_input(self, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 4096 or any(c in value for c in "\r\n\x00"):
            raise PanelError("Enter one command of at most 4096 characters.")
        if not self.lock.acquire(blocking=False):
            raise PanelError("A server operation is in progress.", 409)
        try:
            if not self.running():
                raise PanelError("Server is not running.", 409)
            self.process.stdin.write(value + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise PanelError("Could not send command; the process may have stopped.", 409) from exc
        finally:
            self.lock.release()


class Registry:
    def __init__(self, store, data_dir, emit=None, command=None, installer=None,
                 start_delay=0.35, stop_timeout=15):
        self.store = store
        self.data_dir = Path(data_dir)
        self.emit = emit or (lambda *args: None)
        self.command = command or (lambda instance, executable: [str(executable)])
        self.installer = installer or install
        self.start_delay = start_delay
        self.stop_timeout = stop_timeout
        self.jobs = {}
        self.jobs_lock = threading.RLock()
        self.instances = {row["id"]: Instance(self, row) for row in store.all_servers()}
        self.mutation_lock = threading.RLock()
        self.threads = []
        self.closing = threading.Event()

    def get(self, server_id):
        try:
            return self.instances[server_id]
        except (KeyError, TypeError):
            raise PanelError("Server not found.", 404)

    def all(self):
        with self.mutation_lock:
            return [instance.snapshot() for instance in self.instances.values()]

    def check_ports(self, server_id, config):
        for other in self.instances.values():
            if other.id == server_id:
                continue
            try:
                other_config = read_config(other.directory)
            except PanelError:
                continue
            if config["Port"] == other_config["Port"]:
                raise PanelError("Port is already assigned to another managed instance.", 409)

    @staticmethod
    def probe_ports(config):
        family = socket.AF_INET6 if ":" in config["IP"] else socket.AF_INET
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                with socket.socket(family, kind) as probe:
                    if family == socket.AF_INET6:
                        # BeamMP disables V6ONLY for both TCP and UDP. Probe
                        # the same dual-stack bind, including IPv4 conflicts.
                        probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                    if os.name == "nt":
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    probe.bind((config["IP"], config["Port"]))
            except OSError as exc:
                raise PanelError("The configured TCP/UDP port is occupied or the bind IP is unavailable.", 409) from exc

    def create(self, name, port, auth_key=None):
        values = default_config(name)
        values["Port"] = port
        values["AuthKey"] = require_auth_key(auth_key)
        validate_config(values)
        with self.mutation_lock:
            self.check_ports(None, values)
            directory = self.data_dir / "instances" / str(uuid.uuid4())
            directory.mkdir(parents=True)
            write_config(directory, values)
            (directory / "Resources" / "Client").mkdir(parents=True)
            (directory / "Resources" / "Server").mkdir(parents=True)
            row = self.store.add_server(name, directory)
            instance = Instance(self, row)
            self.instances[instance.id] = instance
            return instance

    @contextmanager
    def idle(self, server_id):
        instance = self.get(server_id)
        if not instance.lock.acquire(blocking=False):
            raise PanelError("A server operation is in progress.", 409)
        try:
            if self.closing.is_set():
                raise PanelError("Panel is shutting down.", 503)
            # A caller may have been waiting while this instance was removed.
            if self.instances.get(server_id) is not instance:
                raise PanelError("Server not found.", 404)
            if instance.running():
                raise PanelError("Stop the server before making this change.", 409)
            yield instance
        finally:
            instance.lock.release()

    def delete(self, server_id, confirmation, delete_files=False):
        if type(delete_files) is not bool:
            raise PanelError("delete_files must be a boolean.")
        with self.idle(server_id) as instance:
            with self.mutation_lock:
                row = self.store.server(server_id)
                if confirmation != row["name"]:
                    raise PanelError("Type the server name exactly to confirm deletion.")
                if instance.reader:
                    instance.reader.join(timeout=2)
                    if instance.reader.is_alive():
                        raise PanelError("Wait for the server console to finish before deleting.", 409)
                if delete_files:
                    directory = instance.directory
                    resolved = directory.resolve()
                    protected = (self.data_dir.resolve(), Path(__file__).resolve().parent)
                    other_paths = []
                    for other in self.instances.values():
                        if other.id == server_id:
                            continue
                        other_paths.append(other.directory.resolve())
                        try:
                            general = load_document(other.directory).unwrap().get("General", {})
                            resources = general.get("ResourceFolder", "Resources") if isinstance(general, dict) else None
                            if isinstance(resources, str) and resources.strip():
                                resource_path = Path(resources)
                                other_paths.append((resource_path if resource_path.is_absolute() else other.directory / resource_path).resolve())
                        except PanelError:
                            pass
                    if (directory != resolved or resolved.parent == resolved
                            or any(root == resolved or root.is_relative_to(resolved) for root in protected)
                            or any(path.is_relative_to(resolved) or resolved.is_relative_to(path) for path in other_paths)):
                        raise PanelError("This directory overlaps protected data or another instance. Remove it from the panel without deleting files.", 409)
                    try:
                        # Only the resolved, verified instance directory is removed;
                        # external ResourceFolder locations are never recursively deleted.
                        if resolved.exists():
                            shutil.rmtree(resolved)
                    except OSError as exc:
                        raise PanelError("Files could not all be deleted. The server record was retained; check file permissions before retrying.", 422) from exc
                self.store.delete_server(server_id)
                del self.instances[server_id]
            self.emit("server_removed", {"server_id": server_id})

    def import_directory(self, name, path):
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise PanelError("Provide an absolute server directory path.")
        directory = Path(path).resolve()
        if not find_executable(directory):
            raise PanelError("No compatible BeamMP executable found in this directory.", 422)
        with self.mutation_lock:
            try:
                row = self.store.add_server(name, directory)
            except sqlite3.IntegrityError as exc:
                raise PanelError("This directory is already registered.", 409) from exc
            instance = Instance(self, row)
            self.instances[instance.id] = instance
            return instance

    def save_config(self, server_id, values):
        with self.idle(server_id) as instance:
            return self.save_config_locked(instance, values)

    def save_config_locked(self, instance, values):
        """Internal helper: caller must hold the instance's idle lock."""
        validate_config(values)
        with self.mutation_lock:
            merged = {**read_config(instance.directory), **values}
            self.check_ports(instance.id, merged)
            write_config(instance.directory, values)
            if "Name" in values:
                self.store.update(instance.id, name=values["Name"])
            instance.refresh_secret()
            instance.set_state("stopped")
        return read_config(instance.directory)

    def operation(self, server_id, action):
        if action not in {"install", "start", "stop", "restart"}:
            raise PanelError("Unknown operation.", 404)
        instance = self.get(server_id)
        with self.jobs_lock:
            if self.closing.is_set():
                raise PanelError("Panel is shutting down.", 503)
            if not instance.lock.acquire(blocking=False):
                raise PanelError("A server operation is already in progress.", 409)
            if self.instances.get(server_id) is not instance:
                instance.lock.release()
                raise PanelError("Server not found.", 404)
            if action in {"start", "install"} and instance.running():
                instance.lock.release()
                raise PanelError("Server is already running.", 409)
            job_id = str(uuid.uuid4())
            job = {"id": job_id, "server_id": server_id, "action": action, "state": "running",
                   "progress": 0, "message": "Starting operation"}
            # Bound completed operation history without evicting active work.
            for key in list(self.jobs):
                if len(self.jobs) < 200:
                    break
                if self.jobs[key]["state"] != "running":
                    del self.jobs[key]
            self.jobs[job_id] = job

            def progress(percent, message):
                with self.jobs_lock:
                    job.update(progress=percent, message=message)

            def run():
                try:
                    if action == "install":
                        instance.set_state("installing")
                        version = self.installer(instance.directory, progress, self.closing.is_set)
                        self.store.update(server_id, version=version)
                        instance.set_state("stopped")
                    else:
                        if action in {"stop", "restart"}:
                            instance._stop()
                        if action in {"start", "restart"}:
                            instance._start()
                    with self.jobs_lock:
                        job.update(state="succeeded", progress=100, message=f"{action.capitalize()} completed")
                except Exception as exc:
                    message = instance.redact(str(exc)) if isinstance(exc, PanelError) else "Operation failed. Check file permissions, executable compatibility, and the console."
                    instance.set_state("running" if instance.running() else "error", message)
                    with self.jobs_lock:
                        job.update(state="failed", message=message)
                finally:
                    instance.lock.release()

            thread = threading.Thread(target=run, daemon=True)
            self.threads = [item for item in self.threads if item.is_alive()]
            self.threads.append(thread)
            thread.start()
            return dict(job)

    def job(self, job_id):
        with self.jobs_lock:
            if job_id not in self.jobs:
                raise PanelError("Operation not found; it may belong to an earlier panel session.", 404)
            return dict(self.jobs[job_id])

    def reconcile(self):
        for row in self.store.all_servers():
            if not row["process_pid"]:
                continue
            try:
                terminate_owned_tree(row["process_pid"], row["process_created"], row["process_executable"])
            except psutil.NoSuchProcess:
                pass
            except (psutil.AccessDenied, psutil.TimeoutExpired) as exc:
                raise RuntimeError("Cannot clean up a previously owned server process; stop it manually before starting the panel.") from exc
            self.store.update(row["id"], process_pid=None, process_created=None, process_executable=None)

    def shutdown(self):
        self.closing.set()
        for thread in self.threads:
            thread.join(timeout=45)
        failed = []
        for instance in self.instances.values():
            try:
                with instance.lock:
                    instance._stop()
            except Exception:
                failed.append(instance.id)
        if failed:
            raise RuntimeError("Some server processes could not be stopped. Their ownership records were retained; stop them manually or restart the panel to reconcile them.")
