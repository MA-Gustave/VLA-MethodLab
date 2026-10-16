#!/bin/bash
set -euo pipefail
: "${TEST102_OUTPUT:?}" "${TEST102_SOURCE:?}" "${TEST102_TOOL:?}" "${TEST102_CORPUS:?}"
cd "$TEST102_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST102_OUTPUT/status102.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST102_OUTPUT/status102.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio102-cloudv.log"}\n' > "$TEST102_OUTPUT/status102.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST102_OUTPUT/tools/test102_diagnostic.py" --output "$TEST102_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + adaptive benchmark; other Test102 attempts fail.
exec 9>"$(dirname "$TEST102_OUTPUT")/test102-exclusive.lock"
if ! flock -n 9; then echo "TEST102: another Test102 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST102_OUTPUT/status102.json"
python3 "$TEST102_TOOL" build --source "$TEST102_SOURCE" --output "$TEST102_OUTPUT" --arch riscv64 --cxx g++

python3 "$TEST102_TOOL" run --output "$TEST102_OUTPUT" --corpus "$TEST102_CORPUS" --explore-seconds 14400 --max-seconds 23400
