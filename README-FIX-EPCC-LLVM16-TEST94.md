# EPCC Test 94 — LLVM16 RVV 1.0 probe fix (2026-10-13)

The EPCC attempt at 2026-10-13 21:32 UTC successfully transferred the checked
source archive and selected Slurm node `rvc02`. **It did not submit a Slurm
job**, because a local cross-compiler probe failed on the x86 login node.

The previous probe referred to the old RVV intrinsic `vsetvl_e8m1` rather than
`__riscv_vsetvl_e8m1`. LLVM16 exposed `<riscv_vector.h>` but rejected that
legacy spelling. The probe now checks standard RVV 1.0 intrinsics, then still
requires working RISC-V C++ linking and an ELF with RISC-V machine type 243.

## Install (no terminal required)

1. Close Lab Studio (remote benchmarks already launched can continue).
2. Unzip the `RVV-VLA-Lab_EPCC_TEST94_LLVM16_PROBE_FIX_DROP_ROOT.zip` file into
   `C:\mycode\Simdjson\RVV-VLA-Lab\` and replace existing files.
3. Restart Studio. Select EPCC; detect nodes and select `rvc02` if idle.
4. Start Test 94. Observe the `EPCC build` log and wait for **`Slurm job submitted`**
   before disconnecting. The compiler probe is not itself a running test.

The fix does not alter the native benchmark, engine, SSH passwords, MFA, node
selection, Cloud-V code or previously downloaded results.

If the *new* EPCC build reports a different failure (for example, missing C++
libraries or an error compiling simdjson), preserve that message. The real
EPCC toolchain cannot be exercised by these local regression tests.

Local regression: `tools/test94_epcc_probe_fix.py` (compiler selection mocked).
