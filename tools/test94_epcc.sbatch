#!/bin/bash
#SBATCH --job-name=rvvlab-test94
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=01:08:00
#SBATCH --output=test94-slurm-%j.out
#SBATCH --error=test94-slurm-%j.err
# EPCC: submit ONLY to an actual RVV 1.0 compute node (e.g. Milk-V Jupiter).
# Set --nodelist using a VERIFIED node name from sinfo; do not assume the login host is RVV.
set -euo pipefail
: "${TEST94_SOURCE:?Must export TEST94_SOURCE=/path/to/engine}"
: "${TEST94_OUTPUT:?Must export TEST94_OUTPUT=/path/to/PREBUILT/run}"
: "${TEST94_TOOL:?Must export TEST94_TOOL=/path/to/test94_native.py}"
if [ "$(uname -m)" != 'riscv64' ]; then
  echo 'REFUSED: this is not a RISC-V compute node' >&2; exit 5
fi
if [ ! -f "$TEST94_OUTPUT/test94_A2_O3" ]; then
  echo 'Missing cross-built A2 binary in shared output directory' >&2; exit 6
fi
python3 "$TEST94_TOOL" run-only \
  --source "$TEST94_SOURCE" --output "$TEST94_OUTPUT" --seconds 3600
