#!/bin/bash
set -euo pipefail
: "${TEST106_OUTPUT:?}" "${TEST106_CANDIDATE:?}" "${TEST106_SOURCE:?}" "${TEST106_TOOL:?}" "${TEST106_CORPUS:?}" "${TEST106_CONFORMANCE:?}"
cd "$TEST106_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST106_OUTPUT/status106.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST106_OUTPUT/status106.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio106-cloudv.log"}\n' > "$TEST106_OUTPUT/status106.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST106_OUTPUT/tools/test106_diagnostic.py" --output "$TEST106_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + overnight benchmark; other Test106 attempts fail.
exec 9>"$(dirname "$TEST106_OUTPUT")/test106-exclusive.lock"
if ! flock -n 9; then echo "TEST106: another Test106 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST106_OUTPUT/status106.json"
python3 "$TEST106_TOOL" build --source "$TEST106_SOURCE" --output "$TEST106_OUTPUT" --arch riscv64 --cxx g++ --candidate-package "$TEST106_CANDIDATE"

python3 "$TEST106_TOOL" run --output "$TEST106_OUTPUT" --corpus "$TEST106_CORPUS" --conformance "$TEST106_CONFORMANCE" --explore-seconds 3600 --max-seconds 7200
