"""Exercise the actual platform scripts with disposable installations/data."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    wheel = Path(sys.argv[1]).resolve()
    root = Path(__file__).resolve().parents[1]
    script_environment = {**os.environ, "BEAMMPY_PYTHON": sys.executable}
    with tempfile.TemporaryDirectory(prefix="beammpy-installers-") as temporary:
        work = Path(temporary)
        program, data = work / "program files", work / "panel data"
        if os.name == "nt":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            assert shell
            def script(name, *arguments):
                return [shell, "-NoProfile", "-File", str(root / "scripts" / f"{name}.ps1"), *map(str, arguments)]
        else:
            def script(name, *arguments):
                return ["sh", str(root / "scripts" / f"{name}.sh"), *map(str, arguments)]
        install_args = ["--install-dir", program, "--wheel", wheel]
        if len(sys.argv) > 2:
            install_args.extend(["--wheelhouse", Path(sys.argv[2]).resolve()])
        subprocess.run(script("install", *install_args, "--data-dir", data), check=True, env=script_environment)
        state = json.loads((program / "installation.json").read_text())
        python = Path(state["active"]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        seed = """
import sys
from pathlib import Path
from beammpy import create_app
data=Path(sys.argv[1])
(data/'.env').write_text('PRESERVE=disposable-fixture\\n')
app=create_app({'DATA_DIR':data,'SECRET_KEY':'installer-test-only'})
try:
    client=app.test_client()
    token=client.get('/api/auth/session').json['csrf_token']
    assert client.post('/api/auth/setup',json={'username':'smoke-owner','password':'installer-test-password'},headers={'X-CSRF-Token':token}).status_code==201
    instance=app.extensions['registry'].create('Preserved fixture',39001,'disposable-key')
    (instance.directory/'owner.txt').write_text('preserve owner content')
finally:
    app.extensions['shutdown']()
"""
        subprocess.run([str(python), "-I", "-c", seed, str(data)], check=True)
        before = {str(path.relative_to(data)): path.read_bytes() for path in data.rglob("*") if path.is_file() and path.name != ".panel.lock"}
        holder = subprocess.Popen([str(python), "-I", "-u", "-c",
                                   "import sys,portalocker; lock=portalocker.Lock(sys.argv[1],mode='a',timeout=0); "
                                   "lock.acquire(); print('locked',flush=True); sys.stdin.read(1); lock.release()",
                                   str(data / ".panel.lock")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            assert holder.stdout.readline().strip() == "locked"
            denied = subprocess.run(script("update", *install_args), capture_output=True, text=True, env=script_environment)
            assert denied.returncode != 0
            assert json.loads((program / "installation.json").read_text()) == state
        finally:
            holder.communicate("\n", timeout=10)
        subprocess.run(script("update", *install_args), check=True, env=script_environment)
        after = json.loads((program / "installation.json").read_text())
        assert after["active"] != state["active"] and after["previous"] == state["active"]
        assert Path(state["active"]).is_dir()
        assert {str(path.relative_to(data)): path.read_bytes() for path in data.rglob("*") if path.is_file() and path.name != ".panel.lock"} == before
        if os.name == "nt":
            launcher = [shell, "-NoProfile", "-File", str(program / "beammpy.ps1"), "list-users"]
        else:
            launcher = ["sh", str(program / "beammpy.sh"), "list-users"]
        listed = subprocess.run(launcher, capture_output=True, text=True, check=True, env=script_environment)
        assert "smoke-owner  administrator  enabled" in listed.stdout
        print(f"{sys.platform}: real install/update/active-panel rejection/installed launcher passed; disposable data preserved byte-for-byte.")


if __name__ == "__main__":
    main()
