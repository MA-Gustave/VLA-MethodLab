#!/bin/bash
#SBATCH --job-name=rvvlab-t104
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=07:30:00
#SBATCH --output=slurm104-%j.out
#SBATCH --error=slurm104-%j.err
set -euo pipefail
: "${TEST104_OUTPUT:?}" "${TEST104_TOOL:?}" "${TEST104_CORPUS:?}" "${TEST104_CONFORMANCE:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST104_OUTPUT/slurm104-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST104_OUTPUT"/slurm104-*.err "$TEST104_OUTPUT"/slurm104-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST104_OUTPUT/slurm104-runtime.log"
    python3 "$TEST104_OUTPUT/tools/test104_diagnostic.py" --output "$TEST104_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST104_OUTPUT"
exec 9>"$(dirname "$TEST104_OUTPUT")/test104-exclusive.lock"
if ! flock -n 9; then echo "Another Test104 is already running" >&2; exit 73; fi

python3 "$TEST104_TOOL" run --output "$TEST104_OUTPUT" --corpus "$TEST104_CORPUS" --conformance "$TEST104_CONFORMANCE" --explore-seconds 14400 --max-seconds 23400
