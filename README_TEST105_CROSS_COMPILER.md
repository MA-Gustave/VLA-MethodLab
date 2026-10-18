# Test 105 — GCC × LLVM Cross-Compiler Stage 2 Matrix

**For Cloud-V (SpacemiT X60) and EPCC `rvc02` (SpacemiT X60).** This is a *compiler attribution* experiment, not an automatic optimization deployment. The same pinned RVV fork and the same fixed Stage 2 optimization source are compiled under **both GCC and LLVM on each machine**. No production engine files are modified.

## What does Test 105 test?

Test 104 showed small, opposing effects of Stage 2 `SIMPLE_RUN` / `NL4` on 18 public JSON documents: ≈ +0.3% EPCC (LLVM 16) and ≈ −0.3% to −0.7% Cloud-V (GCC). Since both machines use SpacemiT X60-class CPUs, **compiler code generation is a hypothesis**, not an established explanation. Test 105 tests that hypothesis by running both compilers on both machines.

### Eight binaries per machine (a strict, complete matrix)

| Compiled with GCC | Compiled with Clang/LLVM | Source/meaning |
|---|---|---|
| `GCC_OFFICIAL_504` | `LLVM_OFFICIAL_504` | Pinned official simdjson 5.0.4, **fallback** backend |
| `GCC_A2_G16384` | `LLVM_A2_G16384` | Pinned unchanged RVV A2, 16-KiB threshold |
| `GCC_A2_SIMPLE_RUN` | `LLVM_A2_SIMPLE_RUN` | Stage 2 consecutive simple escapes |
| `GCC_A2_NL4` | `LLVM_A2_NL4` | Stage 2 simple escapes + four `\\n` pair specialization |

Binary ELF-64 RISC-V identity, **SHA-256**, compiler executable, `--version` line and all compiler flags are recorded. Both compilers use common `-O3`, `-std=c++17`, `-march=rv64gcv`, `-mabi=lp64d` and the same A2 source/flags. On EPCC Clang also requires `--target=riscv64-unknown-linux-gnu`, as in earlier campaigns. No GCC or LLVM result is labeled available before its binary actually compiles. GCC 12.x and LLVM 16.x may expose different RVV intrinsics support: unsupported combinations **fail with a diagnostic before Slurm**; they are never silently replaced by one compiler.

### Main scientific comparison

1. **Same-machine GCC vs LLVM** for the *unchanged* A2 source.
2. **Same-machine patch vs unchanged A2 under GCC** and independently **under LLVM**; this is the real Stage 2 incremental gain.
3. **Compiler × patch interaction**: `(LLVM_patch / LLVM_A2) / (GCC_patch / GCC_A2)` on each document (geometric average after paired rounds). A value greater than 1 means the patch benefits relatively more under LLVM on **that machine**.
4. Each candidate versus the **official fallback compiled by the same compiler** (RVV-vs-fallback baseline; not an isolated patch contribution).
5. Only after receiving both machines' archives, compare the direction of the compiler interactions. **Do not pool raw throughput across machines.**

### Inputs and checks

- 18 public **simdjson-data** JSON documents at pinned commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`.
- Pinned **JSONTestSuite** at commit `1ef36fa01286573e846ac449e8683f8833c5b26a`: full `y_`/`n_`/`i_` checks and transformation cases across **all eight** variants. Invalid/indeterminate cases never become speed samples. The tiny valid `y_` files are separately labeled and not merged with public documents.
- Separate synthetic stress probes of escaped JSON, with independent explore/confirm seeds. Synthetic probes diagnose mechanisms; they do not represent real-world prevalence.
- Correct canonical DOM output across **all eight** binaries before measuring; each group's eight variants are measured in randomized order. Each round uses GCC and LLVM unchanged A2 anchor measurements before and after.
- Full JSON input and source/overlay hash checks; per-machine separate runs and ZIP archives; terminal failures produce diagnostic ZIPs when possible.

## Schedule

| Part | Time |
|---|---:|
| Exploratory measurements | 4 h |
| Independent-seed confirmation | 2 h 30 |
| Worker time budget | 6 h 30 |
| EPCC Slurm reservation | 7 h 30 |

**Compilation and Slurm waiting are extra.** Eight native Cloud-V binaries may require significant compilation time. An incorrect/missing compiler can fail in the preflight/build phase, yielding **zero** measurements and a diagnostic rather than a misleading partial cross-compiler result.

## Compiler availability: important preflight

Neither machine's **second compiler** has been confirmed live from this environment. Test 105 checks compiler presence and links a tiny RVV C++ ELF-64 executable for **each** compiler before building the full matrix. The on-machine preflight is authoritative. Before launching, you can check manually:

**Cloud-V SSH:**

```bash
uname -m
command -v g++
g++ --version | head -1
command -v clang++ || command -v clang++-16 || command -v clang++-17 || command -v clang++-18
```

If native `clang++` is unavailable, the **Cloud-V Test 105 Run refuses the launch before a source transfer**, with a clear explanation. **Do not assume clang is already installed.** On Cloud-V, the compiler must itself target RISC-V (the ELF/intrinsic link probe tests this).

**EPCC login SSH:**

```bash
module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0
command -v riscv64-unknown-linux-gnu-g++ || command -v riscv64-linux-gnu-g++
command -v clang++
```

The GCC C++ cross compiler must support the fork's RVV 1.0 C++ intrinsic API, not merely output generic RISC-V code. If the required toolchain is missing or incompatible, Test 105 stops **before Slurm** with detailed `studio105-build.log` / `probe105_*.log`. Installing/updating compiler toolchains is **not** performed by the ZIP or by the benchmark.

## Installation and launch

1. You must have the **full latest MethodLab** with functional Test 104 installed, including the Test 104 manifest and tools. Back up `studio/` and `tools/`.
2. Close the separate EPCC and Cloud-V Studio windows when no local transfer/launch is active.
3. Extract this **one ZIP directly inside** `C:\mycode\Simdjson\VLA-MethodLab\` (DROP ROOT), accepting replacements. Never extract inside an extra Test105 subfolder.
4. Reopen both Studios. In **JSON Corpus**, verify **Performance** and **Conformance**. Existing verified packages need not be downloaded again.
5. In **Tests → 105**, click **Refresh → Run** once for each profile. Check the Cloud-V compiler-availability message; if it fails, do not keep clicking Run. EPCC only submits after **all eight** builds pass and a Slurm Job ID is returned.
6. Wait for the Cloud-V remote detached-process confirmation / EPCC Slurm Job ID before closing the Studio windows. After that the remote runs continue unattended.
7. Use **Refresh** and **Download** to retrieve each machine's validated SHA-256-checked `test105_results.zip`. Failed jobs should also have a diagnostic archive when packaging was possible.

Cloud-V results: `test105-cloudv-runs/test105-.../test105_results.zip` beneath the configured remote RVV Lab root. EPCC results: `test105-epcc-runs/test105-.../test105_results.zip`.

## Validation scope

- Studio source, UI, corpus and artifact checks: **134 local regression tests passed** on a reconstructed full Lab under a virtual GUI display.
- Test 105's standalone nine-case suite covers eight-variant completeness, compiler–patch interactions, JSONTestSuite byte integrity, manifest routing, official-vs-A2 ratios, and error ZIP semantics.
- x86_64 GCC locally compiled and ran the reference/SIMPLE_RUN/NL4 C++ Stage 2 paths on a mixed Unicode/escaped JSON sample, producing identical canonical DOM output; the test harness passed a Clang++ syntax check. **This is not RISC-V validation**.
- No access to either remote compiler environment or Slurm for direct Test 105 execution. A missing/incompatible compiler will stop before expensive benchmarking; such a stop is **not a benchmark result**.

**No production code change or automatic optimization promotion.**
