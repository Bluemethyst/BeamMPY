#!/bin/sh
set -eu
exec sh "$(dirname "$0")/beammpy.sh" update "$@"
