#!/bin/bash
set -euo pipefail
: "${TEST98_OUTPUT:?}" "${TEST98_SOURCE:?}" "${TEST98_TOOL:?}" "${TEST98_CORPUS:?}"
cd "$TEST98_OUTPUT"
trap 'rc=$?; if [ "$rc" -ne 0 ] && [ ! -f "$TEST98_OUTPUT/status98.json" ]; then printf '\''{"state":"failed","phase":"build","rows":0,"reason":"Build failed; inspect studio98-cloudv.log"}\n'\'' > "$TEST98_OUTPUT/status98.json"; fi' EXIT
python3 "$TEST98_TOOL" build --source "$TEST98_SOURCE" --output "$TEST98_OUTPUT" --arch riscv64 --cxx g++
python3 "$TEST98_TOOL" run --output "$TEST98_OUTPUT" --corpus "$TEST98_CORPUS" --seconds 3600 --repeat-seconds 900
