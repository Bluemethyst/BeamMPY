"""Owned-process metrics and bounded, instance-scoped aggregate player history."""
from collections import deque
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time

import psutil

from .configuration import load_document
from .errors import PanelError

RANGES = {"1h": (3600, 10), "24h": (86400, 300), "7d": (7 * 86400, 1800), "30d": (30 * 86400, 3600)}
RETENTION = 30 * 86400
RECENT_RETENTION = 86400
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def plugin_bytes(token):
    return Path(__file__).with_name("telemetry.lua").read_bytes().replace(b"__TOKEN__", token.encode("ascii"))


class Statistics:
    def __init__(self, registry, interval=5):
        self.registry, self.store = registry, registry.store
        self.interval = interval
        self.lock = threading.RLock()
        self.baselines, self.current, self.players = {}, {}, {}
        self.stop = threading.Event()
        self.thread = None
        self.last_prune = 0
        with self.store.connection() as db:
            self.plugins = {row["server_id"]: dict(row) for row in db.execute("SELECT * FROM statistics_plugins")}

    def start(self):
        self.thread = threading.Thread(target=self._run, name="beammpy-statistics", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                raise RuntimeError("Statistics collector did not stop.")

    def _run(self):
        while not self.stop.wait(self.interval):
            self.collect()

    def collect(self, now=None):
        now = time.time() if now is None else now
        with self.registry.mutation_lock:
            instances = list(self.registry.instances.values())
        for instance in instances:
            if self.stop.is_set():
                break
            try:
                self.sample(instance, now)
            except (OSError, sqlite3.Error, psutil.Error):
                # A disappearing process or inaccessible DB must not kill collection
                # for every other server or interrupt its console reader.
                with self.lock:
                    self.current.pop(instance.id, None)
        with self.registry.mutation_lock, self.lock:
            # Servers can be created while the snapshot above is being sampled.
            active = set(self.registry.instances)
            for mapping in (self.baselines, self.current, self.players, self.plugins):
                for key in list(mapping):
                    if key not in active:
                        mapping.pop(key, None)
        if not self.stop.is_set() and now - self.last_prune >= 3600:
            try:
                self.prune(now)
                self.last_prune = now
            except sqlite3.Error:
                pass

    def prune(self, now):
        with self.store.connection() as db:
            db.execute("DELETE FROM statistics_minutes WHERE minute < ?", (int(now - RETENTION) // 60 * 60,))
            db.execute("DELETE FROM statistics_recent WHERE time < ?", (int(now - RECENT_RETENTION) // 10 * 10,))

    def _record(self, server_id, now, cpu=None, memory=None, players=None, joins=0):
        with self.store.connection() as db:
            # Both resolutions commit together. Identifiers come only from this
            # fixed internal list, never from request parameters.
            for table, column, seconds in (("statistics_minutes", "minute", 60), ("statistics_recent", "time", 10)):
                db.execute(f"""INSERT INTO {table}
                    (server_id,{column},cpu_sum,cpu_n,cpu_peak,memory_sum,memory_n,memory_peak,players_peak,player_n,joins)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(server_id,{column}) DO UPDATE SET
                    cpu_sum=cpu_sum+excluded.cpu_sum,cpu_n=cpu_n+excluded.cpu_n,
                    cpu_peak=CASE WHEN excluded.cpu_peak IS NULL THEN cpu_peak WHEN cpu_peak IS NULL THEN excluded.cpu_peak ELSE max(cpu_peak,excluded.cpu_peak) END,
                    memory_sum=memory_sum+excluded.memory_sum,memory_n=memory_n+excluded.memory_n,
                    memory_peak=CASE WHEN excluded.memory_peak IS NULL THEN memory_peak WHEN memory_peak IS NULL THEN excluded.memory_peak ELSE max(memory_peak,excluded.memory_peak) END,
                    players_peak=CASE WHEN excluded.players_peak IS NULL THEN players_peak WHEN players_peak IS NULL THEN excluded.players_peak ELSE max(players_peak,excluded.players_peak) END,
                    player_n=player_n+excluded.player_n,joins=joins+excluded.joins""",
                           (server_id, int(now) // seconds * seconds, cpu or 0, int(cpu is not None), cpu,
                            memory or 0, int(memory is not None), memory, players, int(players is not None), joins))

    def sample(self, instance, now):
        with self.lock:
            process = instance.process
            if not instance.running():
                self.baselines.pop(instance.id, None)
                self.current.pop(instance.id, None)
                self.players.pop(instance.id, None)
                return
            row = self.store.server(instance.id)
            if not row or row["process_pid"] != process.pid:
                return
            observed = psutil.Process(process.pid)
            created = observed.create_time()
            if (row["process_created"] is None or abs(created - row["process_created"]) >= .01
                    or os.path.normcase(observed.exe()) != os.path.normcase(row["process_executable"] or "")):
                self.current.pop(instance.id, None)
                self.baselines.pop(instance.id, None)
                return
            with observed.oneshot():
                times = observed.cpu_times()
                cpu_time = times.user + times.system
                memory = observed.memory_info().rss / 1024**2
            clock = time.monotonic()
            old = self.baselines.get(instance.id)
            cpu = None
            if old and old[0] is process and clock > old[1] and cpu_time >= old[2]:
                cpu = (cpu_time - old[2]) / (clock - old[1]) * 100
            if instance.process is not process or not instance.running():
                return
            self.baselines[instance.id] = (process, clock, cpu_time)
            self._record(instance.id, now, cpu=cpu, memory=memory)
            self.current[instance.id] = {"process": process, "time": now, "cpu": cpu,
                                         "memory": memory, "created": created}

    def ingest(self, instance, process, text, now=None):
        """Consume only this installation's framed aggregate output, never commands."""
        now = time.time() if now is None else now
        with self.lock:
            plugin = self.plugins.get(instance.id)
            if not plugin or instance.process is not process:
                return False
            clean = ANSI.sub("", text).lstrip("\r >")
            prefix = "BEAMMPY_STATS:" + plugin["token"] + ":"
            if not clean.startswith(prefix):
                return False
            # Keep framed telemetry out of the human console, even if malformed.
            try:
                if len(clean) > 2048:
                    return True
                data = json.loads(clean[len(prefix):])
                if not isinstance(data, dict) or data.get("version") != 1:
                    return True
                epoch = data.get("epoch")
                if not isinstance(epoch, str) or not 1 <= len(epoch) <= 100:
                    return True
                for key, maximum in (("sequence", 10**12), ("online", 4096), ("joins", 10**12)):
                    if type(data.get(key)) is not int or not 0 <= data[key] <= maximum:
                        return True
                old = self.players.get(instance.id)
                if old and old["process"] is process:
                    if epoch in old["previous_epochs"]:
                        return True
                    same = old["epoch"] == epoch
                    if same and (data["sequence"] <= old["sequence"] or data["joins"] < old["joins"]):
                        return True
                    previous = deque(old["previous_epochs"], maxlen=16)
                    if not same:
                        previous.append(old["epoch"])
                    delta = data["joins"] - old["joins"] if same else data["joins"]
                else:
                    previous, delta = deque(maxlen=16), data["joins"]
                if delta > 1000000:
                    return True
                self._record(instance.id, now, players=data["online"], joins=delta)
                self.players[instance.id] = {**data, "process": process, "time": now, "previous_epochs": previous}
            except (ValueError, TypeError, sqlite3.Error):
                pass
            return True

    def snapshot(self, instance, range_name="24h", now=None):
        if range_name not in RANGES:
            raise PanelError("Choose a statistics range: 1h, 24h, 7d or 30d.")
        now = time.time() if now is None else now
        duration, bucket = RANGES[range_name]
        start = int(now - duration) // bucket * bucket
        table, column = ("statistics_recent", "time") if range_name == "1h" else ("statistics_minutes", "minute")
        source_interval = 10 if range_name == "1h" else 60
        cutoff = int(now - duration) // source_interval * source_interval
        with self.store.connection() as db:
            rows = db.execute(f"""SELECT ({column} / ?) * ? AS time,
                sum(cpu_sum)/nullif(sum(cpu_n),0) AS cpu, max(cpu_peak) AS cpu_peak,
                sum(memory_sum)/nullif(sum(memory_n),0) AS memory, max(memory_peak) AS memory_peak,
                max(players_peak) AS players, sum(joins) AS joins, sum(player_n) AS player_n
                FROM {table} WHERE server_id=? AND {column}>=? AND {column}<=?
                GROUP BY 1 ORDER BY 1""", (bucket, bucket, instance.id, cutoff, int(now))).fetchall()
        indexed = {row["time"]: dict(row) for row in rows}
        history = []
        for stamp in range(start, int(now) // bucket * bucket + 1, bucket):
            row = indexed.get(stamp)
            history.append({"time": stamp, "cpu": row["cpu"] if row else None,
                            "cpu_peak": row["cpu_peak"] if row else None,
                            "memory": row["memory"] if row else None,
                            "memory_peak": row["memory_peak"] if row else None,
                            "players": row["players"] if row else None,
                            "joins": row["joins"] if row and row["player_n"] else None})
        with self.lock:
            running = instance.running()
            current = self.current.get(instance.id)
            valid = current and current["process"] is instance.process
            fresh = valid and 0 <= now - current["time"] <= max(15, self.interval * 3)
            players = self.players.get(instance.id)
            player_fresh = (running and players and players["process"] is instance.process
                            and 0 <= now - players["time"] <= 20)
            plugin = instance.id in self.plugins
            live = {"status": "stopped" if not running else "live" if fresh else "stale" if valid else "unavailable",
                    "time": current["time"] if running and valid else None,
                    "cpu": current["cpu"] if running and fresh else None,
                    "memory": current["memory"] if running and fresh else None,
                    "uptime": max(0, now - current["created"]) if running and fresh else None,
                    "players": players["online"] if player_fresh else None,
                    "player_status": "disabled" if not plugin else "stopped" if not running else "live" if player_fresh else "waiting"}
        return {"server_id": instance.id, "range": range_name, "bucket_seconds": bucket,
                "live": live, "history": history, "telemetry_enabled": plugin,
                "summary": {"peak_players": max((row["players"] for row in history if row["players"] is not None), default=None),
                            "joins": sum(row["joins"] or 0 for row in history) if any(row["joins"] is not None for row in history) else None}}

    @staticmethod
    def _unlinked(path, base):
        if not path.is_relative_to(base):
            raise PanelError("Player statistics require a private instance-local resource directory.", 409)
        for item in [path, *path.parents]:
            if item.is_symlink() or (item.exists() and getattr(item.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
                raise PanelError("Linked resource paths cannot be used for the statistics plugin.", 409)
            if item == base:
                break
        if path.resolve() != path:
            raise PanelError("Linked resource paths cannot be used for the statistics plugin.", 409)

    def configure_plugin(self, server_id, enabled):
        if type(enabled) is not bool:
            raise PanelError("enabled must be a boolean.")
        with self.registry.idle(server_id) as instance, self.registry.mutation_lock, self.lock:
            base = instance.directory
            value = load_document(base).unwrap().get("General", {}).get("ResourceFolder", "Resources")
            if not isinstance(value, str) or not value.strip():
                raise PanelError("ResourceFolder must be a directory path.", 422)
            root = Path(value) if Path(value).is_absolute() else base / value
            # Reject noncanonical/linked paths before creating any plugin files.
            self._unlinked(root, base)
            for other in self.registry.instances.values():
                if other.id == server_id:
                    continue
                other_value = load_document(other.directory).unwrap().get("General", {}).get("ResourceFolder", "Resources")
                if not isinstance(other_value, str) or not other_value.strip():
                    raise PanelError("Resource ownership could not be verified.", 409)
                other_root = Path(other_value)
                other_root = (other_root if other_root.is_absolute() else other.directory / other_root).resolve()
                if any(root.is_relative_to(path) or path.is_relative_to(root) for path in (other.directory, other_root)):
                    raise PanelError("Player statistics require private resources, not shared resources.", 409)
            directory = root / "Server" / "BeamMPYStatistics"
            target = directory / "main.lua"
            self._unlinked(target, base)
            existing = self.plugins.get(server_id)
            if existing:
                if Path(existing["path"]) != target:
                    raise PanelError("ResourceFolder changed. Restore its previous location before managing this plugin.", 409)
                if (not target.is_file() or target.stat().st_nlink != 1
                        or target.read_bytes() != plugin_bytes(existing["token"])
                        or set(directory.iterdir()) != {target}):
                    raise PanelError("The statistics plugin was changed externally. Existing files were preserved.", 409)
                if enabled:
                    return
                target.unlink()
                directory.rmdir()
                with self.store.connection() as db:
                    db.execute("DELETE FROM statistics_plugins WHERE server_id=?", (server_id,))
                self.plugins.pop(server_id, None)
                self.players.pop(server_id, None)
            elif enabled:
                if directory.exists():
                    raise PanelError("A plugin already uses the BeamMPYStatistics directory. Existing files were preserved.", 409)
                token = secrets.token_hex(16)
                directory.mkdir(parents=True)
                created = False
                try:
                    with target.open("xb") as stream:
                        created = True
                        stream.write(plugin_bytes(token))
                    with self.store.connection() as db:
                        db.execute("INSERT INTO statistics_plugins(server_id,path,token) VALUES(?,?,?)", (server_id, str(target), token))
                except BaseException:
                    if created:
                        target.unlink(missing_ok=True)
                    if not any(directory.iterdir()):
                        directory.rmdir()
                    raise
                self.plugins[server_id] = {"path": str(target), "token": token}
