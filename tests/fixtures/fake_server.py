"""A disposable line-oriented process; never starts BeamMP or opens a game port."""
from pathlib import Path
import sys
import time

print("READY " + Path.cwd().name, flush=True)
if Path("early-exit").exists():
    sys.exit(4)
for line in sys.stdin:
    command = line.rstrip("\r\n")
    if command == "exit":
        if Path("ignore-exit").exists():
            while True:
                time.sleep(1)
        print("GOODBYE", flush=True)
        break
    print("ECHO " + command, flush=True)
