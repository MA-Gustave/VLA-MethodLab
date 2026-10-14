#!/bin/sh
# One-command launcher for Linux login/compute nodes. Never needs sudo.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$HERE/tools/machine_probe.py" "$@"
