#!/bin/bash
set -euo pipefail
: "${TEST99_OUTPUT:?}" "${TEST99_SOURCE:?}" "${TEST99_TOOL:?}" "${TEST99_CORPUS:?}"
cd "$TEST99_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST99_OUTPUT/status99.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST99_OUTPUT/status99.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio99-cloudv.log"}\n' > "$TEST99_OUTPUT/status99.json"
    fi
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + 8-hour benchmark; other Test99 attempts fail.
exec 9>"$(dirname "$TEST99_OUTPUT")/test99-exclusive.lock"
if ! flock -n 9; then echo "TEST99: another Test99 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST99_OUTPUT/status99.json"
python3 "$TEST99_TOOL" build --source "$TEST99_SOURCE" --output "$TEST99_OUTPUT" --arch riscv64 --cxx g++
rm -f "$TEST99_OUTPUT/status99.json"
python3 "$TEST99_TOOL" run --output "$TEST99_OUTPUT" --corpus "$TEST99_CORPUS" --seconds 28800 --confirmation-seconds 7200
