#!/bin/bash
#SBATCH --job-name=rvvlab-t99
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=08:20:00
#SBATCH --output=slurm99-%j.out
#SBATCH --error=slurm99-%j.err
set -euo pipefail
: "${TEST99_OUTPUT:?}" "${TEST99_TOOL:?}" "${TEST99_CORPUS:?}"
trap 'rc=$?; if [ "$rc" = 0 ]; then state=completed; else state=failed; fi; printf '\''{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n'\'' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST99_OUTPUT/slurm99-exit.json"' EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST99_OUTPUT"
exec 9>"$(dirname "$TEST99_OUTPUT")/test99-exclusive.lock"
if ! flock -n 9; then echo "Another Test99 is already running" >&2; exit 73; fi
rm -f "$TEST99_OUTPUT/status99.json"
python3 "$TEST99_TOOL" run --output "$TEST99_OUTPUT" --corpus "$TEST99_CORPUS" --seconds 28800 --confirmation-seconds 7200
