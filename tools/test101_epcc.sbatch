#!/bin/bash
#SBATCH --job-name=rvvlab-t101
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=07:30:00
#SBATCH --output=slurm101-%j.out
#SBATCH --error=slurm101-%j.err
set -euo pipefail
: "${TEST101_OUTPUT:?}" "${TEST101_TOOL:?}" "${TEST101_CORPUS:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST101_OUTPUT/slurm101-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST101_OUTPUT"/slurm101-*.err "$TEST101_OUTPUT"/slurm101-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST101_OUTPUT/slurm101-runtime.log"
    python3 "$TEST101_OUTPUT/tools/test101_diagnostic.py" --output "$TEST101_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST101_OUTPUT"
exec 9>"$(dirname "$TEST101_OUTPUT")/test101-exclusive.lock"
if ! flock -n 9; then echo "Another Test101 is already running" >&2; exit 73; fi

python3 "$TEST101_TOOL" run --output "$TEST101_OUTPUT" --corpus "$TEST101_CORPUS" --min-seconds 3600 --confirm-seconds 1800 --max-seconds 21600
