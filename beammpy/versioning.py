"""Panel version from the bundled manifest, with SemVer 2.0 precedence."""
import json
from pathlib import Path
import re


_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def semver(value):
    """Return (core, prerelease); build metadata never changes precedence."""
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Invalid SemVer version")
    match = _SEMVER.fullmatch(value)
    if not match:
        raise ValueError("Invalid SemVer version")
    pre = tuple(match[4].split('.')) if match[4] else ()
    if any(part.isascii() and part.isdigit() and len(part) > 1 and part[0] == '0' for part in pre):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeros")
    return tuple(int(match[i]) for i in (1, 2, 3)), pre


def is_newer(candidate, installed):
    new_core, new_pre = semver(candidate)
    old_core, old_pre = semver(installed)
    if new_core != old_core:
        return new_core > old_core
    if not new_pre or not old_pre:
        return bool(old_pre) and not new_pre
    for new, old in zip(new_pre, old_pre):
        if new == old:
            continue
        if new.isdigit() and old.isdigit():
            return int(new) > int(old)
        if new.isdigit() != old.isdigit():
            return not new.isdigit()
        return new > old
    return len(new_pre) > len(old_pre)


def manifest_version(raw):
    def unique_keys(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("Duplicate manifest key")
            data[key] = value
        return data
    try:
        data = json.loads(raw, object_pairs_hook=unique_keys)
    except RecursionError as exc:
        raise ValueError("Manifest nesting exceeds limits") from exc
    if not isinstance(data, dict) or set(data) != {"version"}:
        raise ValueError("Invalid version manifest")
    semver(data["version"])
    return data["version"]


# This is the manifest shipped with this panel, never a managed BeamMP version
# or the working directory's pyproject/frontend metadata.
VERSION = manifest_version(Path(__file__).with_name("version.json").read_bytes())
