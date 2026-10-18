#!/bin/bash
#SBATCH --job-name=rvvlab-t103
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=07:30:00
#SBATCH --output=slurm103-%j.out
#SBATCH --error=slurm103-%j.err
set -euo pipefail
: "${TEST103_OUTPUT:?}" "${TEST103_TOOL:?}" "${TEST103_CORPUS:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST103_OUTPUT/slurm103-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST103_OUTPUT"/slurm103-*.err "$TEST103_OUTPUT"/slurm103-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST103_OUTPUT/slurm103-runtime.log"
    python3 "$TEST103_OUTPUT/tools/test103_diagnostic.py" --output "$TEST103_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST103_OUTPUT"
exec 9>"$(dirname "$TEST103_OUTPUT")/test103-exclusive.lock"
if ! flock -n 9; then echo "Another Test103 is already running" >&2; exit 73; fi

python3 "$TEST103_TOOL" run --output "$TEST103_OUTPUT" --corpus "$TEST103_CORPUS" --explore-seconds 14400 --max-seconds 23400
