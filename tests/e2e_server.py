"""Browser-test host with disposable data and child processes, never real BeamMP."""
from pathlib import Path
import os
import sys
import tempfile
import zipfile
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from beammpy import create_app
from waitress import create_server


def fake_install(directory, progress, cancelled):
    name = "BeamMP-Server.exe" if os.name == "nt" else "BeamMP-Server.fixture"
    target = Path(directory) / name
    target.write_text("browser-test fixture", encoding="utf-8")
    target.chmod(0o700)
    progress(100, "Fixture installed")
    return "fixture-v1"


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="beammpy-browser-") as data:
        app = create_app({"DATA_DIR": data, "SECRET_KEY": "browser-test-only",
                          "PROCESS_COMMAND": lambda instance, executable: [sys.executable, "-u", str(Path(__file__).parent / "fixtures" / "fake_server.py")],
                          "INSTALLER": fake_install, "START_DELAY": 0.15, "STOP_TIMEOUT": 0.3})
        imported = Path(data) / "import-ready"
        imported.mkdir()
        fake_install(imported, lambda *args: None, lambda: False)
        (imported / "ServerConfig.toml").write_text('[General]\nName="Import fixture"\nPort=38011\n', encoding="utf-8")
        fixtures = Path(data) / "test-fixtures"
        fixtures.mkdir()
        with zipfile.ZipFile(fixtures / "browser-trails.zip", "w") as archive:
            archive.writestr("levels/browser_canyon/info.json", json.dumps({"title": "Browser Canyon"}))
            archive.writestr("vehicles/browser_car/info.json", "{}")
        with zipfile.ZipFile(fixtures / "server-archive.zip", "w") as archive:
            for entry in imported.iterdir():
                archive.write(entry, "Imported Server/" + entry.name)
        server = create_server(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8791, threads=32)
        try:
            server.run()
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            app.extensions["shutdown"]()
