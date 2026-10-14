# Test 94 — One-hour A2 tuning / hardware comparison (Cloud-V + EPCC)

**Status:** launchable source patch, not remotely run. 100% native RVV1.0; no changes to production, no automatic winner promotion. Both machines use the **same test94 native script and deterministic JSON workload design**.

## Decision from archived Test 93 (2026-10-13)

Test 93 `night-20261013T120347Z-1ad1e5.zip`: 4,184 fully paired four-way groups; 12,552 A2/official/compositions rows plus 4,184 packed_plain control rows. Holdout relative to A2: packed_plain **0.955x**, best composition P2345c07522b1 **0.723x**, official VLS256 **0.676x**. Stage1 losses dominated the experimental strategies. Thus A2, compiled `-O3 -march=rv64gcv -mabi=lp64d`, is the presumptive winner. The `A2_LTO` variant adds `-flto` as a **new hypothesis**, not a proven improvement; packed_plain is a controlled reference, not an assumed optimization.

| Variant | Code/config | Purpose |
|---|---|---|
| `A2_O3` | A2 level 2, packed off; GCC `-O3` | Recommended baseline |
| `A2_LTO` | Same A2, `-flto` compile and link | Potential better codegen (unknown) |
| `packed_plain` | A2 level 2 with packed-control/index-writer on, runtime exploration OFF | Reference from Test93 |

All variants are VLA RVV1.0 (`-march=rv64gcv`) and **not** the VLS256-only binary, because EPCC's target may have a different VLEN. On-node VLEN will be measured, not assumed. If LTO or packed_plain build fails, that optional variant is marked failed rather than fabricating results; A2 is mandatory.

**Scope:** ~13 deterministic JSON family/size anchors including ASCII/dense/escaped/UTF-8/Unicode/long strings/nesting and mixed 16 KiB regions; 64 KiB, 1 MiB, and 8 MiB. Full-DOM result equivalence with fallback is checked for every variant/corpus before benchmarking; valid/invalid JSON smoke checked first. Randomized order within groups. Last 20% wall-time is a **fresh-seed frozen holdout**, independent of prior measurements. Stages 1 and 2 are independent diagnostics, not the sum of DOM timing. One hot CPU pinned within the machine's available affinity; Slurm allocates two CPUs to permit orchestrator separation. Record source, compiler, binaries SHA256 and hardware. 200 MiB free-disk check. No secrets or `.env` files are included.

## Windows: install patch into your existing project

Extract `RVV-VLA-Lab_Test94_1H_DROP_ROOT.zip` at `C:\mycode\Simdjson\RVV-VLA-Lab\` and overwrite files. It **adds** only files (`tools/test94_native.py`, `tools/test94_epcc.sbatch`, `README-TEST94-1H.md`), and makes **no changes to Studio**, existing test profiles or campaigns.

### Cloud-V: build + run directly, up to 3600 seconds total

Transfer your current `engine/` and `tools/test94_native.py` onto Cloud-V using your normal deployment method, or use the existing source checkout. From a directory containing `engine/` and `tools/`:

```bash
python3 tools/test94_native.py all --source engine --output "$HOME/rvvlab-test94/cloudv-$(date -u +%Y%m%dT%H%M%SZ)" --seconds 3600
```

**Compilation, native correctness and benchmarking all fall within the same 1h deadline**. The run saves `results94.csv`, `REPORT_94.md`, `machine94.json`, `builds.json`, `summary94.json`, `status94.json` and `test94_results.zip`.

### EPCC: cross-build on login, run on RVV1.0 compute node only

1. Connect with `ssh epcc-login` via your configured SSH jump (passphrase/MFA as required). Transfer **this project's modified engine source** and script to a working directory on the login host. **Do not run the benchmark on the login node.**
2. On `riscv-login`, from the project directory:

```bash
module load riscv64-linux/gnu-12.2
mkdir -p "$HOME/rvvlab-test94"
python3 tools/test94_native.py build-only --source engine \
  --output "$HOME/rvvlab-test94/epcc-prebuilt" \
  --cxx riscv64-unknown-linux-gnu-g++
sinfo -N -o '%N %P %t %f'  # Select a genuine Milk-V Jupiter / K1 RVV1.0 node
```

3. Verify the selected node's RVV1.0 capability and permitted partition / account, then submit. Replace `ACTUAL_RVV10_NODE` (and account/partition if required) with values obtained from the site admin or `sinfo`:

```bash
export TEST94_SOURCE="$PWD/engine"
export TEST94_OUTPUT="$HOME/rvvlab-test94/epcc-prebuilt"
sbatch --export=ALL,TEST94_SOURCE="$TEST94_SOURCE",TEST94_OUTPUT="$TEST94_OUTPUT" \
  --nodelist=ACTUAL_RVV10_NODE tools/test94_epcc.sbatch
squeue -u "$USER"
```

**EPCC compute runtime:** 3600 seconds on the allocated RISC-V node. The batch reservation is 1h08m, leaving time to initialize and export evidence. Cross-compilation on x86 is a separate preliminary phase and **not counted** in the one-hour compute runtime. This is deliberate: the official EPCC docs say to compile on `riscv-login` and execute on RISC-V Slurm nodes. Slurm may require `-A <account>` or a partition; `nx09` is a SAFE project, not necessarily the Slurm account string. **Do not use the older Test91–93 256-bit VLEN-only preflight on unknown EPCC VLEN.**

**If cross-compilation fails:** inspect `build_A2_O3_compile.log`; check availability of `riscv64-unknown-linux-gnu-g++` and RVV1.0 support. Do not interpret a failed compile as a measured performance regression. Optional LTO or packed failures do not invalidate a successful A2 baseline.

### Stop, status, and results

- Cloud-V foreground: Ctrl+C stops the script (collects any completed measurements).
- EPCC: `squeue -u "$USER"` to inspect and `scancel JOB_ID` to stop; Slurm output in `test94-slurm-JOBID.out`.
- `cat "$RUN/status94.json"`, `cat "$RUN/REPORT_94.md"` for progress.
- Retrieve `test94_results.zip` (and `.sha256`); **do not paste or upload secret `.env` files**.

### Cross-machine comparison

After retrieving each run's `test94_results.zip` to the same PC:

```powershell
python tools\test94_native.py compare cloudv_test94_results.zip epcc_test94_results.zip
```

Writes `TEST94_COMPARISON.md`. Compares per-machine holdout ratios and absolute A2 rates only on matching corpus family/layout/**exact bytes SHA256**. Do not pool raw GB/s across unmatched workloads or compare different processors as if they were identical. Do not attribute a throughput difference solely to CPU: toolchains, frequency, VLEN and thermals may vary.

### Preflight / caveats

- Uses the existing exact simdjson v5.0.3 patched `engine/` source and its known v5 native split-stage benchmark harness; **not standalone** without engine source.
- Test was exercised locally with mocks/synthetic runners; **no EPCC/Cloud-V native performance results are claimed yet**.
- This patch deliberately **does not** attempt automated SSH MFA, save passwords, change `.env.epcc` or launch remote jobs for you. Use your interactive authenticated SSH session to transfer and launch the test.
- A historical archive is only used for selecting the experiment plan; Test94 does not change or reuse the archived benchmark results as new measurements.
