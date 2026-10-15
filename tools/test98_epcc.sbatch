#!/bin/bash
#SBATCH --job-name=rvvlab-t98
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=01:10:00
#SBATCH --output=slurm98-%j.out
#SBATCH --error=slurm98-%j.err
set -euo pipefail
: "${TEST98_OUTPUT:?}" "${TEST98_TOOL:?}" "${TEST98_CORPUS:?}"
trap 'rc=$?; if [ "$rc" = 0 ]; then state=completed; else state=failed; fi; printf '\''{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n'\'' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST98_OUTPUT/slurm98-exit.json"' EXIT
if [ "$(uname -m)" != 'riscv64' ]; then echo 'Not RISC-V compute' >&2; exit 5; fi
cd "$TEST98_OUTPUT"
python3 "$TEST98_TOOL" run --output "$TEST98_OUTPUT" --corpus "$TEST98_CORPUS" --seconds 3600 --repeat-seconds 900
