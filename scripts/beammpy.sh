#!/bin/sh
set -eu
exec "${BEAMMPY_PYTHON:-python3}" "$(dirname "$0")/manage.py" "$@"
