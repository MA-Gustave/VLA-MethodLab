#!/bin/bash
set -euo pipefail
: "${TEST104_OUTPUT:?}" "${TEST104_SOURCE:?}" "${TEST104_TOOL:?}" "${TEST104_CORPUS:?}" "${TEST104_CONFORMANCE:?}"
cd "$TEST104_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST104_OUTPUT/status104.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST104_OUTPUT/status104.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio104-cloudv.log"}\n' > "$TEST104_OUTPUT/status104.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST104_OUTPUT/tools/test104_diagnostic.py" --output "$TEST104_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + overnight benchmark; other Test104 attempts fail.
exec 9>"$(dirname "$TEST104_OUTPUT")/test104-exclusive.lock"
if ! flock -n 9; then echo "TEST104: another Test104 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST104_OUTPUT/status104.json"
python3 "$TEST104_TOOL" build --source "$TEST104_SOURCE" --output "$TEST104_OUTPUT" --arch riscv64 --cxx g++

python3 "$TEST104_TOOL" run --output "$TEST104_OUTPUT" --corpus "$TEST104_CORPUS" --conformance "$TEST104_CONFORMANCE" --explore-seconds 14400 --max-seconds 23400
