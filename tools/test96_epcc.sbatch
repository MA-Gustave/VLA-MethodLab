#!/bin/bash
#SBATCH --job-name=rvvlab-t96
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=08:10:00
#SBATCH --output=slurm96-%j.out
#SBATCH --error=slurm96-%j.err
# WARNING: run only via Slurm on an EPCC RISC-V compute node.
# Exactly 28,800 seconds of benchmark budget AFTER Slurm allocation.
# 10 minutes extra are reserved for process startup and output finalisation.
set -euo pipefail
: "${TEST96_SOURCE:?}" "${TEST96_OUTPUT:?}" "${TEST96_TOOL:?}"
report_exit() {
  rc=$?
  trap - EXIT
  state=completed
  if [ "$rc" -ne 0 ]; then state=failed; fi
  printf '{"state":"%s","return_code":%d,"slurm_job_id":"%s"}\n' "$state" "$rc" "${SLURM_JOB_ID:-unknown}" > "$TEST96_OUTPUT/slurm96-exit.json"
  echo "TEST96 EPCC SLURM EXIT state=$state rc=$rc"
}
trap report_exit EXIT
if [ "$(uname -m)" != 'riscv64' ]; then
  echo 'REFUSED: x86 login is not a RISC-V compute node' >&2
  exit 5
fi
if [ ! -f "$TEST96_OUTPUT/test96_A2_REF" ]; then
  echo 'Cross-compiled A2_REF binary absent' >&2
  exit 6
fi
cd "$TEST96_OUTPUT"
echo "TEST96 EPCC job=$SLURM_JOB_ID node=$(hostname) started=$(date -u +%FT%TZ)"
python3 "$TEST96_TOOL" run-only --source "$TEST96_SOURCE" --output "$TEST96_OUTPUT" --seconds 28800
