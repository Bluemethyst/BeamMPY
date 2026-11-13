import os
import platform
import time
from pathlib import Path

import distro
import requests

from .errors import PanelError

RELEASE_URL = "https://api.github.com/repos/BeamMP/BeamMP-Server/releases/latest"


def asset_name(system=None, distribution=None, version=None, machine=None):
    system = system or platform.system()
    machine = machine or platform.machine()
    arch = {"AMD64": "x86_64", "amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    if system == "Windows" and arch == "x86_64":
        return "BeamMP-Server.exe"
    if system == "Linux":
        distribution = distribution or distro.id()
        version = version or distro.version()
        if distribution == "ubuntu":
            version = ".".join(version.split(".")[:2])
        elif distribution == "debian":
            version = version.split(".")[0]
        else:
            raise PanelError("No automatic build for this Linux distribution. Import a compatible installation.", 422)
        return f"BeamMP-Server.{distribution}.{version}.{arch}"
    raise PanelError("No automatic build for this OS/architecture. Import a compatible installation.", 422)


def install(directory, progress, cancelled, http=None):
    """Download an official stable asset; an incomplete file is never executable."""
    http = http or requests.Session()
    owned = isinstance(http, requests.Session)
    target = None
    temporary = None
    try:
        progress(1, "Finding an official release")
        expected = asset_name()
        with http.get(RELEASE_URL, timeout=(10, 30), headers={"Accept": "application/vnd.github+json"}) as response:
            response.raise_for_status()
            release = response.json()
        if release.get("prerelease") or release.get("draft"):
            raise PanelError("No stable BeamMP release was returned.", 502)
        asset = next((item for item in release.get("assets", []) if item["name"] == expected), None)
        if not asset:
            raise PanelError(f"This release has no {expected} build. Import a compatible installation.", 422)
        url = asset.get("browser_download_url", "")
        if not url.startswith("https://github.com/BeamMP/BeamMP-Server/releases/download/"):
            raise PanelError("Release contains an unexpected download location.", 502)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / expected
        if target.exists():
            raise PanelError("A server executable already exists; it will not be overwritten.", 409)
        temporary = directory / (expected + ".download")
        received = 0
        deadline = time.monotonic() + 300
        with http.get(url, stream=True, timeout=(10, 30)) as response:
            response.raise_for_status()
            total = int(asset.get("size", 0))
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(65536):
                    if cancelled() or time.monotonic() > deadline:
                        raise PanelError("Installation cancelled or timed out. Retry when ready.", 503)
                    if chunk:
                        received += len(chunk)
                        if received > 512 * 1024 * 1024:
                            raise PanelError("Release asset exceeds the download limit.", 502)
                        stream.write(chunk)
                        progress(min(95, int(received * 95 / total)) if total else 25, "Downloading BeamMP")
                stream.flush()
                os.fsync(stream.fileno())
        if received == 0 or (total and received != total):
            raise PanelError("Download was incomplete. Retry installation.", 502)
        if cancelled():
            raise PanelError("Installation cancelled.", 503)
        if platform.system() != "Windows":
            temporary.chmod(0o700)
        os.replace(temporary, target)
        progress(100, "Installed")
        return release.get("tag_name", "unknown")
    except requests.RequestException as exc:
        raise PanelError("Could not download BeamMP. Check internet access or GitHub rate limits, then retry.", 502) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
        if owned:
            http.close()
