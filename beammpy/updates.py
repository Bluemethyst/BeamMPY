"""Lazy, single-flight panel update checks. No network work during startup."""
import sys
import threading
import time

import requests

from .versioning import VERSION, is_newer, manifest_version, semver


MANIFEST_URL = "https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/beammpy/version.json"
WINDOWS_COMMAND = "iwr -useb https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 | iex"
UBUNTU_COMMAND = "curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh | sh"
SUCCESS_TTL = 6 * 60 * 60
FAILURE_TTL = 60 * 60
MAX_BYTES = 4096


def fetch_version():
    # No redirects, credentials, client-provided URLs or commands from the wire.
    # Read a tiny response incrementally so a drip-fed body also has a deadline.
    deadline = time.monotonic() + 8
    with requests.get(MANIFEST_URL, timeout=(2, 3), stream=True, allow_redirects=False,
                      auth=lambda request: request,  # Suppress implicit .netrc authentication.
                      headers={"Accept": "application/json", "User-Agent": "BeamMPY-update-check"}) as response:
        if response.status_code != 200:
            raise ValueError("Version manifest unavailable")
        content_type = response.headers.get("Content-Type", "").split(';')[0].strip().lower()
        if content_type not in {"application/json", "text/plain"}:
            raise ValueError("Unexpected manifest content type")
        if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
            raise ValueError("Version manifest too large")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=1):
            if time.monotonic() > deadline or len(body) + len(chunk) > MAX_BYTES:
                raise ValueError("Version manifest exceeded limits")
            body.extend(chunk)
        return manifest_version(body.decode("utf-8"))


class UpdateChecker:
    def __init__(self, *, installed=VERSION, host_os=None, fetch=fetch_version, clock=time.monotonic):
        semver(installed)
        self.installed = installed
        platform = sys.platform if host_os is None else host_os
        self.host_os = "windows" if platform == "win32" else "linux" if platform == "linux" else "unsupported"
        self.command = WINDOWS_COMMAND if self.host_os == "windows" else UBUNTU_COMMAND if self.host_os == "linux" else None
        self._fetch, self._clock = fetch, clock
        self._lock = threading.Lock()
        self._next_check = 0
        self._state = "unchecked"
        self._available = None
        self._worker = None

    def snapshot(self):
        with self._lock:
            if self._state != "checking" and self._clock() >= self._next_check:
                self._state, self._available = "checking", None
                self._worker = threading.Thread(target=self._check, name="panel-update-check", daemon=True)
                self._worker.start()
            return {"installed_version": self.installed, "available_version": self._available,
                    "update_available": self._state == "available", "status": self._state,
                    "host_os": self.host_os, "command": self.command}

    def _check(self):
        try:
            version = self._fetch()
            newer = is_newer(version, self.installed)
            state, available, ttl = ("available" if newer else "current"), version, SUCCESS_TTL
        except (requests.RequestException, ValueError, TypeError, OSError):
            # Failure is silent, negatively cached and cannot retain a stale notice.
            state, available, ttl = "unavailable", None, FAILURE_TTL
        with self._lock:
            self._state, self._available = state, available
            self._next_check = self._clock() + ttl
