"""Instance-scoped maps, client mods and bounded server ZIP imports."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
import zlib

from .configuration import load_document, read_config, write_config
from .errors import PanelError
from .manager import find_executable

STOCK_MAPS = {
    "gridmap_v2": "Gridmap V2", "johnson_valley": "Johnson Valley",
    "automation_test_track": "Automation Test Track", "east_coast_usa": "East Coast, USA",
    "hirochi_raceway": "Hirochi Raceway", "italy": "Italy", "jungle_rock_island": "Jungle Rock Island",
    "industrial": "Industrial Site", "small_island": "Small Island, USA", "smallgrid": "Grid, Small, Pure",
    "utah": "Utah, USA", "west_coast_usa": "West Coast, USA", "driver_training": "Driver Training",
    "derby": "Derby Arenas",
}
MAX_FILES = 20000
MAX_EXPANDED = 8 * 1024**3


def archive_entries(archive, max_expanded=MAX_EXPANDED):
    entries = archive.infolist()
    if len(entries) > MAX_FILES or sum(item.file_size for item in entries) > max_expanded:
        raise PanelError("ZIP contains too many files or more than 8 GiB of expanded data.", 413)
    seen = set()
    checked = []
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for item in entries:
        raw = item.filename.replace("\\", "/")
        path = PurePosixPath(raw)
        if (not raw or item.orig_filename != item.filename or raw.startswith("/") or not path.parts
                or any(part in ("..", ".") or ":" in part or part.endswith((" ", "."))
                       or any(ord(c) < 32 for c in part) or part.split(".")[0].upper() in reserved
                       for part in path.parts)):
            raise PanelError("ZIP contains an unsafe file path.", 422)
        key = path.as_posix().casefold()
        mode = stat.S_IFMT(item.external_attr >> 16)
        if key in seen or mode not in (0, stat.S_IFREG, stat.S_IFDIR) or item.flag_bits & 1:
            raise PanelError("ZIP contains duplicate paths, links, special files or encrypted entries.", 422)
        seen.add(key)
        checked.append((item, path))
    return checked


def copy_limited(source, destination, limit):
    size = 0
    while chunk := source.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise PanelError("Upload exceeds the configured size limit.", 413)
        destination.write(chunk)
    return size


def mod_name(value):
    if (not isinstance(value, str) or not value.lower().endswith(".zip") or len(value) > 200
            or any(c in value for c in '/\\:\x00*?<>|"') or value.startswith(".")
            or value.endswith((" ", ".")) or any(ord(c) < 32 for c in value)):
        raise PanelError("Choose a ZIP filename without directory separators or special characters.")
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise PanelError("This filename is reserved by the operating system.")
    return value


class Content:
    def __init__(self, registry, upload_limit=2 * 1024**3):
        self.registry = registry
        self.upload_limit = upload_limit

    @staticmethod
    def resource_dirs(instance):
        read_config(instance.directory)
        value = load_document(instance.directory).unwrap().get("General", {}).get("ResourceFolder", "Resources")
        if not isinstance(value, str) or not value.strip():
            raise PanelError("ResourceFolder must be a directory path.", 422)
        root = Path(value)
        root = (root if root.is_absolute() else instance.directory / root).resolve()
        return root / "Client", root / ".beammpy-disabled"

    @staticmethod
    def inspect_mod(path, enabled):
        result = {"filename": path.name, "enabled": enabled, "size": path.stat().st_size, "maps": [], "error": None}
        try:
            if path.is_symlink() or path.resolve().parent != path.parent.resolve():
                raise PanelError("Linked ZIP files cannot be managed.", 422)
            with zipfile.ZipFile(path) as archive:
                entries = archive_entries(archive)
                if any(name.name.casefold() in {"serverconfig.toml", "users.db", "panel.secret", ".env"}
                       for _, name in entries):
                    raise PanelError("This ZIP contains server configuration or panel data. Use Import server instead of uploading it as a client mod.", 422)
                for item, name in entries:
                    parts = name.parts
                    if len(parts) == 3 and parts[0].lower() == "levels" and parts[2].lower() == "info.json":
                        title = re.sub(r"[_-]+", " ", parts[1]).title()
                        if item.file_size <= 256 * 1024:
                            try:
                                info = json.loads(archive.read(item).decode("utf-8-sig"))
                                label = info.get("title", info.get("name")) if isinstance(info, dict) else None
                                if isinstance(label, str) and label.strip():
                                    title = label[:200]
                            except (ValueError, UnicodeError):
                                pass
                        result["maps"].append({"path": f"/levels/{parts[1]}/info.json", "name": title})
        except (OSError, ValueError, zipfile.BadZipFile, PanelError, RuntimeError, zlib.error) as exc:
            result["error"] = str(exc) if isinstance(exc, PanelError) else "ZIP could not be read. Check its integrity and permissions."
        return result

    def mods(self, instance):
        results = []
        for root, enabled in zip(self.resource_dirs(instance), (True, False)):
            if root.is_symlink() or root.resolve() != root:
                raise PanelError("Mod directories must not be symbolic links or junctions.", 422)
            if root.exists():
                for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
                    if path.is_file() and path.suffix.lower() == ".zip":
                        results.append(self.inspect_mod(path, enabled))
        return results

    def maps(self, instance):
        configured = read_config(instance.directory)["Map"]
        choices = [{"path": f"/levels/{key}/info.json", "name": label, "kind": "stock", "enabled": True, "mod": None}
                   for key, label in STOCK_MAPS.items()]
        for mod in self.mods(instance):
            for item in mod["maps"]:
                existing = next((choice for choice in choices if choice["path"] == item["path"]), None)
                if existing and (existing["enabled"] or not mod["enabled"]):
                    continue
                if existing:
                    choices.remove(existing)
                choices.append({**item, "kind": "custom", "enabled": mod["enabled"] and not mod["error"], "mod": mod["filename"]})
        if configured not in {item["path"] for item in choices}:
            choices.append({"path": configured, "name": "Current custom map", "kind": "custom", "enabled": False, "mod": None})
        return {"current": configured, "maps": sorted(choices, key=lambda item: (item["kind"] != "stock", item["name"].casefold()))}

    def select_map(self, server_id, path):
        with self.registry.idle(server_id) as instance:
            if not any(item["path"] == path and item["enabled"] for item in self.maps(instance)["maps"]):
                raise PanelError("Choose a stock map or a map provided by an enabled mod.", 422)
            self.registry.save_config_locked(instance, {"Map": path})
            return self.maps(instance)

    def toggle_mod(self, server_id, filename, enabled):
        filename = mod_name(filename)
        if type(enabled) is not bool:
            raise PanelError("enabled must be a boolean.")
        with self.registry.idle(server_id) as instance:
            client, disabled = self.resource_dirs(instance)
            self.mods(instance)  # Validate both directory boundaries before modifying them.
            source = (disabled if enabled else client) / filename
            destination = (client if enabled else disabled) / filename
            if source.is_symlink() or source.resolve().parent != source.parent.resolve() or not source.is_file():
                raise PanelError("Mod ZIP not found.", 404)
            if destination.exists():
                raise PanelError("A mod with this name already exists in the destination.", 409)
            details = self.inspect_mod(source, not enabled)
            if enabled and details["error"]:
                raise PanelError(details["error"], 422)
            if not enabled and read_config(instance.directory)["Map"] in {item["path"] for item in details["maps"]}:
                raise PanelError("Select a different map before disabling the mod that provides the current map.", 409)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            return self.mods(instance)

    def upload_mod(self, server_id, filename, stream):
        filename = mod_name(filename)
        with self.registry.idle(server_id) as instance:
            self.mods(instance)
            client, disabled = self.resource_dirs(instance)
            if any(path.name.casefold() == filename.casefold() for root in (client, disabled)
                   if root.exists() for path in root.iterdir()):
                raise PanelError("A mod with this filename already exists. Rename the upload or use the existing mod.", 409)
            client.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".upload-", dir=client.parent) as stage:
                target = Path(stage) / filename
                with target.open("wb") as destination:
                    copy_limited(stream, destination, self.upload_limit)
                details = self.inspect_mod(target, True)
                if details["error"]:
                    raise PanelError(details["error"], 422)
                try:
                    with zipfile.ZipFile(target) as archive:
                        if archive.testzip():
                            raise PanelError("ZIP failed its integrity check.", 422)
                except (zipfile.BadZipFile, RuntimeError, OSError, zlib.error) as exc:
                    raise PanelError("ZIP failed its integrity check.", 422) from exc
                target.rename(client / filename)
            return self.mods(instance)

    def import_local(self, name, value):
        if not isinstance(value, str) or "\x00" in value or not Path(value).is_absolute():
            raise PanelError("Provide an absolute directory or ZIP file path.")
        path = Path(value)
        if path.is_dir():
            return self.registry.import_directory(name, value)
        if not path.is_file() or path.suffix.lower() != ".zip":
            raise PanelError("Choose an existing server folder or a server ZIP archive.", 422)
        with path.open("rb") as stream:
            return self.import_zip(name, stream)

    def import_zip(self, name, stream):
        root = (self.registry.data_dir / "instances").resolve()
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".import-", dir=root) as staging:
            staging = Path(staging)
            uploaded = staging / "server.zip"
            with uploaded.open("wb") as destination:
                copy_limited(stream, destination, self.upload_limit)
            unpacked = staging / "unpacked"
            unpacked.mkdir()
            try:
                with zipfile.ZipFile(uploaded) as archive:
                    for item, relative in archive_entries(archive):
                        target = unpacked.joinpath(*relative.parts)
                        if not target.resolve().is_relative_to(unpacked.resolve()):
                            raise PanelError("ZIP contains an unsafe file path.", 422)
                        if item.is_dir() or item.filename.endswith("\\"):
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(item) as source, target.open("wb") as destination:
                                copy_limited(source, destination, min(item.file_size + 1, MAX_EXPANDED))
                            if target.name.startswith("BeamMP-Server") and not target.name.endswith(".exe"):
                                target.chmod(0o700)
            except (zipfile.BadZipFile, OSError, RuntimeError, ValueError, zlib.error) as exc:
                raise PanelError("Server ZIP could not be extracted. Check the archive and available disk space.", 422) from exc
            candidates = [path.parent for path in unpacked.rglob("ServerConfig.toml") if find_executable(path.parent)]
            if len(candidates) != 1:
                raise PanelError("Server ZIP must contain one ServerConfig.toml beside a compatible BeamMP executable.", 422)
            candidate = candidates[0]
            read_config(candidate)
            document = load_document(candidate)
            # An archive from another machine must not read or write host paths
            # specified by its old ResourceFolder. Its bundled Resources stay local.
            if "ResourceFolder" in document.get("General", {}):
                configured = document["General"]["ResourceFolder"]
                relative = str(configured).replace("\\", "/") if isinstance(configured, str) else ""
                destination = (candidate / relative).resolve()
                # Keep bundled custom resource directories when their relative
                # location remains inside the imported instance.
                portable = (relative and not PurePosixPath(relative).is_absolute()
                            and ":" not in relative and destination.is_relative_to(candidate.resolve()))
                document["General"]["ResourceFolder"] = relative if portable else "Resources"
                from .configuration import write_document
                write_document(candidate, document)
            final = root / str(uuid.uuid4())
            candidate.rename(final)
            try:
                return self.registry.import_directory(name, str(final))
            except Exception:
                # This was generated inside the verified instance root, never a
                # user-supplied directory. Roll back only this unregistered copy.
                if final.parent == root and final.is_dir() and not final.is_symlink():
                    shutil.rmtree(final)
                raise
