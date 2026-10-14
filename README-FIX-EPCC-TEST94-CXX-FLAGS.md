# Test 94 — EPCC LLVM16 CLI argument fix (2026-10-13)

The EPCC attempt on 2026-10-13 at 21:45 UTC successfully deployed the source
archive and **passed** the RVV 1.0 compiler probe on the x86 login node.
Compilation did not begin because `test94_epcc_build.py` invoked
`test94_native.py` with a separate `--cxx-flags` value beginning with
`--target=...`. Python argparse interpreted the value as another option:
`error: argument --cxx-flags: expected one argument`.

**Fix:** pass the value as one argument,
`--cxx-flags=--target=riscv64-unknown-linux-gnu`. For multiple compiler
flags, shell-style quoting is preserved in the single value, then expanded
with `shlex.split` by `test94_native.py`.

## Installation

1. Close Lab Studio (Cloud-V benchmark runs independently on the server).
2. Extract `RVV-VLA-Lab_EPCC_TEST94_CXXFLAGS_ARGFIX_DROP_ROOT.zip` directly into
   `C:\mycode\Simdjson\RVV-VLA-Lab\` and overwrite files.
3. Reopen Lab Studio, select **EPCC**, connect, choose `rvc02` if still idle,
   then **Run Test 94 (1h)**.
4. **Do not disconnect** until Studio reports `Slurm job submitted: ...`.

The prior EPCC attempt did not submit any Slurm job. There are no EPCC
benchmark results to recover from that attempt. Cloud-V need not be rerun.

The patch changes only the EPCC command-line argument handoff, and adds a
regression test. No SSH credentials, `.env.epcc`, engine source or benchmark
measurements are altered. Real compiler/build/Slurm availability on EPCC
remains to be confirmed by the next launch.
