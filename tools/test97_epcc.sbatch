#!/bin/bash
#SBATCH --job-name=rvvlab-t97
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=03:10:00
#SBATCH --output=slurm97-%j.out
#SBATCH --error=slurm97-%j.err
set -euo pipefail
: "${TEST97_SOURCE:?}" "${TEST97_OUTPUT:?}" "${TEST97_TOOL:?}"
trap 'rc=$?; if [ "$rc" = 0 ]; then state=completed; else state=failed; fi; printf '\''{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n'\'' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST97_OUTPUT/slurm97-exit.json"' EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not a RISC-V compute node' >&2; exit 5; fi
cd "$TEST97_OUTPUT"
python3 "$TEST97_TOOL" run-only --source "$TEST97_SOURCE" --output "$TEST97_OUTPUT" --seconds 10800 --holdout 2700
