"""Download the matching official stable asset and run opt-in isolated smoke tests."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from beammpy.installer import install
from beammpy.manager import find_executable


def main():
    with tempfile.TemporaryDirectory(prefix="beammpy-official-smoke-") as directory:
        version = install(directory, lambda percent, message: None, lambda: False)
        print(f"Testing official BeamMP {version} in a disposable private instance.", flush=True)
        environment = {**os.environ, "BEAMMPY_SMOKE_BINARY": str(find_executable(directory))}
        subprocess.run([sys.executable, "-m", "pytest", "tests/test_real_beammp.py", "-q",
                        "--basetemp", str(Path(directory) / "pytest"), "-p", "no:cacheprovider"],
                       env=environment, check=True, cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    main()
