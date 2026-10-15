#!/bin/sh
# Explicit Cloud-V only. Creates a new directory and never overwrites older runs.
set -eu
LAB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUN="${LAB_DIR}/test95-local-$(date -u +%Y%m%dT%H%M%SZ)-$$"
if [ "$(uname -m)" != riscv64 ]; then echo 'Test95 is Cloud-V native riscv64 only' >&2; exit 2; fi
mkdir "$RUN"
exec python3 "$LAB_DIR/tools/test95_native.py" all --source "$LAB_DIR/engine" --output "$RUN" --seconds 28800
