#!/bin/bash
#SBATCH --job-name=rvvlab-t106
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=02:45:00
#SBATCH --output=slurm106-%j.out
#SBATCH --error=slurm106-%j.err
set -euo pipefail
: "${TEST106_OUTPUT:?}" "${TEST106_TOOL:?}" "${TEST106_CORPUS:?}" "${TEST106_CONFORMANCE:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST106_OUTPUT/slurm106-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST106_OUTPUT"/slurm106-*.err "$TEST106_OUTPUT"/slurm106-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST106_OUTPUT/slurm106-runtime.log"
    python3 "$TEST106_OUTPUT/tools/test106_diagnostic.py" --output "$TEST106_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST106_OUTPUT"
exec 9>"$(dirname "$TEST106_OUTPUT")/test106-exclusive.lock"
if ! flock -n 9; then echo "Another Test106 is already running" >&2; exit 73; fi

python3 "$TEST106_TOOL" run --output "$TEST106_OUTPUT" --corpus "$TEST106_CORPUS" --conformance "$TEST106_CONFORMANCE" --explore-seconds 3600 --max-seconds 7200
