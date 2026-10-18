#!/bin/bash
set -euo pipefail
: "${TEST105_OUTPUT:?}" "${TEST105_SOURCE:?}" "${TEST105_TOOL:?}" "${TEST105_CORPUS:?}" "${TEST105_CONFORMANCE:?}"
cd "$TEST105_OUTPUT"
on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ ! -f "$TEST105_OUTPUT/status105.json" ] || grep -Eq '"state"[[:space:]]*:[[:space:]]*"building"' "$TEST105_OUTPUT/status105.json"; then
      printf '{"state":"failed","phase":"build","rows":0,"validated":false,"reason":"Launch/build failed; inspect studio105-cloudv.log"}\n' > "$TEST105_OUTPUT/status105.json"
    fi
  fi
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST105_OUTPUT/tools/test105_diagnostic.py" --output "$TEST105_OUTPUT" --reason 'Cloud-V build/worker failed' || true
  fi
}
trap on_exit EXIT
# Keep the lock for the entire build + overnight benchmark; other Test105 attempts fail.
exec 9>"$(dirname "$TEST105_OUTPUT")/test105-exclusive.lock"
if ! flock -n 9; then echo "TEST105: another Test105 run is active" >&2; exit 73; fi
printf '{"state":"building","phase":"native-build","rows":0,"validated":false}\n' > "$TEST105_OUTPUT/status105.json"
python3 "$TEST105_TOOL" build --source "$TEST105_SOURCE" --output "$TEST105_OUTPUT" --arch riscv64 --gcc g++ --llvm "${TEST105_LLVM:-clang++}"

python3 "$TEST105_TOOL" run --output "$TEST105_OUTPUT" --corpus "$TEST105_CORPUS" --conformance "$TEST105_CONFORMANCE" --explore-seconds 14400 --max-seconds 23400
