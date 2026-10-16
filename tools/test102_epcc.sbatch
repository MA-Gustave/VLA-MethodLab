#!/bin/bash
#SBATCH --job-name=rvvlab-t102
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=07:30:00
#SBATCH --output=slurm102-%j.out
#SBATCH --error=slurm102-%j.err
set -euo pipefail
: "${TEST102_OUTPUT:?}" "${TEST102_TOOL:?}" "${TEST102_CORPUS:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST102_OUTPUT/slurm102-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST102_OUTPUT"/slurm102-*.err "$TEST102_OUTPUT"/slurm102-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST102_OUTPUT/slurm102-runtime.log"
    python3 "$TEST102_OUTPUT/tools/test102_diagnostic.py" --output "$TEST102_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST102_OUTPUT"
exec 9>"$(dirname "$TEST102_OUTPUT")/test102-exclusive.lock"
if ! flock -n 9; then echo "Another Test102 is already running" >&2; exit 73; fi

python3 "$TEST102_TOOL" run --output "$TEST102_OUTPUT" --corpus "$TEST102_CORPUS" --explore-seconds 14400 --max-seconds 23400
