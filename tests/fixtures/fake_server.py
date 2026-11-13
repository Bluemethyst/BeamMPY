"""A disposable line-oriented process; never starts BeamMP or opens a game port."""
from pathlib import Path
import sys
import time

print("READY " + Path.cwd().name, flush=True)
if Path("early-exit").exists():
    sys.exit(4)

import json
import re
import threading

# Optional telemetry fixture exercises the same stdout transport as the Lua plugin.
plugin = Path("Resources/Server/BeamMPYStatistics/main.lua")
stats_token = re.search(r'local token = "([a-f0-9]+)"', plugin.read_text(encoding="utf-8")) if plugin.is_file() else None
stats_lock, stats_stop = threading.Lock(), threading.Event()
stats_sequence, stats_online, stats_joins = 0, 0, 0


def stats_snapshot():
    global stats_sequence
    if stats_token:
        stats_sequence += 1
        print("BEAMMPY_STATS:" + stats_token[1] + ":" + json.dumps({"version": 1, "epoch": "fixture", "sequence": stats_sequence,
                                                               "online": stats_online, "joins": stats_joins}), flush=True)


def stats_loop():
    while not stats_stop.wait(.5):
        with stats_lock:
            stats_snapshot()


if stats_token:
    with stats_lock:
        stats_snapshot()
    threading.Thread(target=stats_loop, daemon=True).start()

for line in sys.stdin:
    command = line.rstrip("\r\n")
    if stats_token and command in {"fixture-player-join", "fixture-player-leave"}:
        with stats_lock:
            if command == "fixture-player-join":
                stats_online += 1
                stats_joins += 1
            else:
                stats_online = max(0, stats_online - 1)
            stats_snapshot()
    if command == "exit":
        if Path("ignore-exit").exists():
            while True:
                time.sleep(1)
        print("GOODBYE", flush=True)
        stats_stop.set()
        break
    print("ECHO " + command, flush=True)
