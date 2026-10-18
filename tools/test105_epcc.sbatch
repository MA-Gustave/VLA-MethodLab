#!/bin/bash
#SBATCH --job-name=rvvlab-t105
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=07:30:00
#SBATCH --output=slurm105-%j.out
#SBATCH --error=slurm105-%j.err
set -euo pipefail
: "${TEST105_OUTPUT:?}" "${TEST105_TOOL:?}" "${TEST105_CORPUS:?}" "${TEST105_CONFORMANCE:?}"
on_exit() {
  rc=$?
  if [ "$rc" = 0 ]; then state=completed; else state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST105_OUTPUT/slurm105-exit.json"
  if [ "$rc" -ne 0 ]; then
    { echo "SLURM exit code $rc; job ${SLURM_JOB_ID:-unknown}"; for f in "$TEST105_OUTPUT"/slurm105-*.err "$TEST105_OUTPUT"/slurm105-*.out; do [ ! -f "$f" ] || { echo "--- $f ---"; tail -n 100 "$f"; }; done; } > "$TEST105_OUTPUT/slurm105-runtime.log"
    python3 "$TEST105_OUTPUT/tools/test105_diagnostic.py" --output "$TEST105_OUTPUT" --reason 'EPCC Slurm worker failed' || true
  fi
}
trap on_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST105_OUTPUT"
exec 9>"$(dirname "$TEST105_OUTPUT")/test105-exclusive.lock"
if ! flock -n 9; then echo "Another Test105 is already running" >&2; exit 73; fi

python3 "$TEST105_TOOL" run --output "$TEST105_OUTPUT" --corpus "$TEST105_CORPUS" --conformance "$TEST105_CONFORMANCE" --explore-seconds 14400 --max-seconds 23400
