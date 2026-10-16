#!/bin/bash
#SBATCH --job-name=rvvlab-t100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=05:00:00
#SBATCH --output=slurm100-%j.out
#SBATCH --error=slurm100-%j.err
set -euo pipefail
: "${TEST100_OUTPUT:?}" "${TEST100_TOOL:?}" "${TEST100_CORPUS:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST100_OUTPUT/slurm100-exit.json"
  if [ "$rc" -ne 0 ]; then
    python3 "$TEST100_OUTPUT/tools/test100_diagnostic.py" --output "$TEST100_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST100_OUTPUT"
exec 9>"$(dirname "$TEST100_OUTPUT")/test100-exclusive.lock"
if ! flock -n 9; then echo "Another Test100 is already running" >&2; exit 73; fi

python3 "$TEST100_TOOL" run --output "$TEST100_OUTPUT" --corpus "$TEST100_CORPUS" --min-seconds 2700 --confirm-seconds 1200 --max-seconds 14400
