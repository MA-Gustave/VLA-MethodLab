#!/bin/bash
set -euo pipefail
: "${TEST101_OUTPUT:?}" "${TEST101_SOURCE:?}" "${TEST101_TOOL:?}" "${TEST101_CORPUS:?}"
cd "$TEST101_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST101_OUTPUT/status101.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST101_OUTPUT/status101.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio101-cloudv.log"}\n' > "$TEST101_OUTPUT/status101.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST101_OUTPUT/tools/test101_diagnostic.py" --output "$TEST101_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + adaptive benchmark; other Test101 attempts fail.
exec 9>"$(dirname "$TEST101_OUTPUT")/test101-exclusive.lock"
if ! flock -n 9; then echo "TEST101: another Test101 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST101_OUTPUT/status101.json"
python3 "$TEST101_TOOL" build --source "$TEST101_SOURCE" --output "$TEST101_OUTPUT" --arch riscv64 --cxx g++

python3 "$TEST101_TOOL" run --output "$TEST101_OUTPUT" --corpus "$TEST101_CORPUS" --min-seconds 3600 --confirm-seconds 1800 --max-seconds 21600
