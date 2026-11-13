import os
from pathlib import Path
import tempfile
import tomlkit

from .errors import PanelError

FIELDS = {
    "Name": (str, "BeamMP server"), "Description": (str, ""),
    "Map": (str, "/levels/gridmap_v2/info.json"), "Port": (int, 30814),
    "MaxPlayers": (int, 8), "MaxCars": (int, 1), "Private": (bool, True),
    "AllowGuests": (bool, True), "LogChat": (bool, True),
    "Debug": (bool, False), "InformationPacket": (bool, True),
    # Match BeamMP's dual-stack default. An IPv4-only listener in 3.9.x
    # fails code C identification when its peer is cast to an IPv6 address.
    "IP": (str, "::"), "Tags": (str, "Freeroam"),
}


def load_document(directory):
    path = Path(directory) / "ServerConfig.toml"
    if not path.exists():
        return tomlkit.document()
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise PanelError("Cannot read ServerConfig.toml. Correct its syntax and file permissions.", 422) from exc


def read_config(directory):
    doc = load_document(directory)
    general = doc.unwrap().get("General", {})
    if not isinstance(general, dict):
        raise PanelError("The General configuration section must be a TOML table.", 422)
    return {**{key: general.get(key, default) for key, (_, default) in FIELDS.items()},
            "has_auth_key": isinstance(general.get("AuthKey"), str) and bool(general["AuthKey"].strip())}


def require_auth_key(value):
    if not isinstance(value, str) or not value.strip():
        raise PanelError("An AuthKey is required. Obtain a key from BeamMP Keymaster.")
    value = value.strip()
    if len(value) > 256 or any(character.isspace() or character == "\x00" for character in value):
        raise PanelError("AuthKey must contain at most 256 characters without whitespace.")
    return value


def validate_config(values):
    if not isinstance(values, dict):
        raise PanelError("Configuration must be an object.")
    unknown = values.keys() - FIELDS.keys() - {"AuthKey"}
    if unknown:
        raise PanelError("Unsupported configuration fields: " + ", ".join(sorted(unknown)))
    for key, value in values.items():
        expected = str if key == "AuthKey" else FIELDS[key][0]
        if type(value) is not expected:
            raise PanelError(f"{key} must be {expected.__name__}.")
        if isinstance(value, str) and ("\x00" in value or len(value) > 10000):
            raise PanelError(f"{key} contains invalid or excessive text.")
    for key, maximum in {"Name": 250, "Description": 1000, "Map": 100, "Tags": 100}.items():
        if key in values and len(values[key]) > maximum:
            raise PanelError(f"{key} must be at most {maximum} characters.")
    if "Port" in values and not 1024 <= values["Port"] <= 65535:
        raise PanelError("Port must be between 1024 and 65535.")
    for key in ("MaxPlayers", "MaxCars"):
        if key in values and not 1 <= values[key] <= 100000:
            raise PanelError(f"{key} must be a positive integer no greater than 100000.")
    if "Name" in values and not values["Name"].strip():
        raise PanelError("Name cannot be empty.")
    if "Map" in values and not values["Map"].startswith("/levels/"):
        raise PanelError("Map must be a /levels/.../info.json path.")
    if "IP" in values:
        import ipaddress
        try:
            ipaddress.ip_address(values["IP"])
        except ValueError as exc:
            raise PanelError("IP must be a valid IPv4 or IPv6 address.") from exc


def write_config(directory, values):
    validate_config(values)
    path = Path(directory) / "ServerConfig.toml"
    doc = load_document(directory)
    if "General" not in doc:
        doc["General"] = tomlkit.table()
    if not isinstance(doc["General"], dict):
        raise PanelError("The General configuration section must be a TOML table.", 422)
    for key, value in values.items():
        doc["General"][key] = value
    write_document(directory, doc)


def write_document(directory, doc):
    path = Path(directory) / "ServerConfig.toml"
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".config-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(tomlkit.dumps(doc))
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    except OSError as exc:
        raise PanelError("Configuration could not be saved. Check directory permissions.", 422) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def default_config(name):
    return {**{key: default for key, (_, default) in FIELDS.items()}, "Name": name}
