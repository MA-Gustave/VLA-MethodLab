#!/bin/bash
set -euo pipefail
: "${TEST100_OUTPUT:?}" "${TEST100_SOURCE:?}" "${TEST100_TOOL:?}" "${TEST100_CORPUS:?}"
cd "$TEST100_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST100_OUTPUT/status100.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST100_OUTPUT/status100.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio100-cloudv.log"}\n' > "$TEST100_OUTPUT/status100.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST100_OUTPUT/tools/test100_diagnostic.py" --output "$TEST100_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + adaptive benchmark; other Test100 attempts fail.
exec 9>"$(dirname "$TEST100_OUTPUT")/test100-exclusive.lock"
if ! flock -n 9; then echo "TEST100: another Test100 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST100_OUTPUT/status100.json"
python3 "$TEST100_TOOL" build --source "$TEST100_SOURCE" --output "$TEST100_OUTPUT" --arch riscv64 --cxx g++

python3 "$TEST100_TOOL" run --output "$TEST100_OUTPUT" --corpus "$TEST100_CORPUS" --min-seconds 2700 --confirm-seconds 1200 --max-seconds 14400
