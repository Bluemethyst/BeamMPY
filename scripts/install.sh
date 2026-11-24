#!/bin/sh
set -eu
# Explicit wheel arguments retain the original offline/manual installer.
if [ "$#" -gt 0 ]; then
    exec sh "$(dirname "$0")/beammpy.sh" install "$@"
fi

command -v python3 >/dev/null 2>&1 || { echo 'Install Python 3.11+ and python3-venv first.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
command -v systemctl >/dev/null 2>&1 || { echo 'Ubuntu with systemd is required.' >&2; exit 1; }
# Leave the shell's script input on the download pipe. Only interactive child
# commands read /dev/tty; redirecting the shell itself can truncate a piped script.
[ -r /dev/tty ] || { echo 'Run this installer from an interactive terminal.' >&2; exit 1; }
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo 'Run as root or install sudo.' >&2; exit 1; }
    sudo -v </dev/tty
fi

script_dir=''
if [ -f "$0" ]; then
    script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fi
if [ -n "$script_dir" ] && [ -f "$script_dir/setup.py" ]; then
    source_dir=$(dirname "$script_dir")
else
    command -v curl >/dev/null 2>&1 || { echo 'Install curl and ca-certificates first.' >&2; exit 1; }
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' 0
    trap 'exit 130' INT
    trap 'exit 143' TERM
    curl -fL --retry 3 'https://codeload.github.com/Bluemethyst/BeamMPY/zip/refs/heads/main' -o "$work/source.zip"
    python3 -m zipfile -e "$work/source.zip" "$work"
    source_dir="$work/BeamMPY-main"
fi
if [ "$(id -u)" -eq 0 ]; then
    python3 "$source_dir/scripts/setup.py" ubuntu --source "$source_dir" </dev/tty
else
    sudo python3 "$source_dir/scripts/setup.py" ubuntu --source "$source_dir" </dev/tty
fi
