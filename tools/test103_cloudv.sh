#!/bin/bash
set -euo pipefail
: "${TEST103_OUTPUT:?}" "${TEST103_SOURCE:?}" "${TEST103_TOOL:?}" "${TEST103_CORPUS:?}"
cd "$TEST103_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST103_OUTPUT/status103.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST103_OUTPUT/status103.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio103-cloudv.log"}\n' > "$TEST103_OUTPUT/status103.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST103_OUTPUT/tools/test103_diagnostic.py" --output "$TEST103_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + overnight benchmark; other Test103 attempts fail.
exec 9>"$(dirname "$TEST103_OUTPUT")/test103-exclusive.lock"
if ! flock -n 9; then echo "TEST103: another Test103 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST103_OUTPUT/status103.json"
python3 "$TEST103_TOOL" build --source "$TEST103_SOURCE" --output "$TEST103_OUTPUT" --arch riscv64 --cxx g++

python3 "$TEST103_TOOL" run --output "$TEST103_OUTPUT" --corpus "$TEST103_CORPUS" --explore-seconds 14400 --max-seconds 23400
