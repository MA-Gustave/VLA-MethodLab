# Test 102 — Overnight escape-density and Stage 1 / Stage 2 attribution

**Targets:** Cloud-V `riscv64` (GCC native), EPCC `rvc02` (LLVM 16 cross-compile + Slurm).  
**Purpose:** Diagnose the RVV A2 dense-escape regression revealed by Tests 97 and 101. **This is a diagnostic campaign, not an automatically applied parser optimization.**

## Install (Windows DROP ROOT)

1. Close both Lab Studio windows **when no local launch / source deployment is in progress**. Existing detached Cloud-V and submitted EPCC jobs are not changed by replacing local Studio files.
2. Back up `studio` and `tools`; extract this ZIP at `C:\mycode\Simdjson\VLA-MethodLab\`, **not** inside a new subfolder.
3. Reopen the independent Cloud-V and EPCC Studio windows and connect to their respective SSH profiles.
4. Under **JSON Corpus → Performance**, check **18 verified files** on PC. The Test 102 launcher automatically syncs them to the selected server, and then strictly verifies every fixture and the pinned commit before build/Slurm.
5. In **Tests → 102**, click **Refresh**, then **Run** once **for each machine**. Do not run another CPU benchmark on the same remote machine concurrently.
6. On EPCC, **wait until a Slurm Job ID is confirmed** before disconnecting/closing Studio. On Cloud-V, wait until the detached process launch is confirmed. After that, the jobs continue remotely and do not require the PC to remain on.
7. Check via **Refresh** (Studio UI stays at its normal ~60-second refresh) and **Download** once an archive exists. Failed or stopped runs also have a diagnostic archive whenever packaging was possible.

**No remote run is started by extracting this ZIP.** The Run action still requires your direct confirmation.

## Night-time schedule and safeguards

| Segment | Budget |
|---|---:|
| Explore, with synthetic seed A | 4 hours |
| Confirm, with independent synthetic seed B | 2 hours 30 minutes |
| Total measurement-worker limit | **6 hours 30 minutes** |
| EPCC Slurm reservation | **7 hours 30 minutes** |

Build and source transfer are additional preparation steps; EPCC compilation happens on the login node **before** Slurm submission. The worker has a strict time budget, but this is **not a guaranteed completion time** if preflight, hardware availability or EPCC scheduler submission fails. EPCC's actual Slurm policy must accept the reservation.

The experiment is non-adaptive by design: the second phase must receive time even if the first phase converges quickly. Completion status is not inferred from elapsed time or the mere existence of a folder.

- Single-machine exclusive lock per Test 102 launch; source checks and anti-contention checks before launch.
- SHA-256 of all public inputs and both fork compilation units; pinned upstream commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`.
- Pinned official **simdjson 5.0.4** and the *same* experimental fork source/engine-plan SHA-256 as Test 101.
- RISC-V ELF-64 header and binary hashes checked before execution; all candidate outputs must agree on canonical DOM output **before timing**.
- CPU affinity pinned, randomized paired measurement order, A2 16 KiB anchors before/after each comparison; drift recorded.
- Atomic status file, CSV groups flushed continuously, partial/failure result archives, ZIP CRC and remote/local SHA-256 verification.
- Distinct output roots: `test102-cloudv-runs` and `test102-epcc-runs`; no Test 100–101 data overwritten.

## Compared binaries

- `OFFICIAL_504`: pinned simdjson 5.0.4, **fallback** backend.
- `A2_REF`: pinned dedicated RVV A2 with dispatch threshold **4 KiB**.
- `A2_G16384`: same RVV A2 source, threshold **16 KiB**, all packed options disabled.

**Important:** official fallback vs A2 RVV compares different backends; it cannot identify the contribution of a threshold alone. A2 16 KiB vs A2 4 KiB isolates the threshold more directly.

## Inputs

- 18 unchanged public performance JSON files (the same pinned files from Tests 100–101).
- 206 distinct synthetic fixtures in `explore` and 206 **byte-distinct** fixtures in `confirm` (same parameter grid, independent seed / filler). There are **no public-derived fragments** in this test, to focus on escape behavior.
- Controlled raw backslash target densities **0, 1, 3, 6, 10, 15, 25, 50%** for `\\n`, `\\\"`, `\\\\`, `\\u0041`, `\\t` workloads, exact-size 8 / 16 KiB files. The `\\u0041` atom spans six raw bytes and therefore cannot achieve a 50% raw backslash density; the **actual** density is recorded per input. Mixtures in the public fixtures are not approximated as independent synthetic documents.
- Separate 4 KiB, 8 KiB and 16 KiB boundary probes with **0, 1, 2, 4, 8, 9, 12, 16 or 32** controlled antislashs, near the beginning of the payload or after byte 512.

## Measurements, metrics and analysis

The harness benchmarks **three real operations**, as independent timings: full public DOM parse, internal Stage 1 indexing, and internal Stage 2 DOM construction/unescaping. It does **not** infer Stage 1 or Stage 2 by subtracting full parse times. Stage rates should **not** be added as if they were independent components of DOM throughput. Short inputs also contain stopwatch overhead; use the pairing and per-document analysis rather than treating microscopic percentages as definitive.

`summary102.json` and `REPORT_102.md` include paired geometric ratios by family, **by requested raw escape density**, and **by exact crossover backslash count and placement**. `results102.csv` preserves all individual records and full input hashes; `inputs102.json` records actual escape densities, byte sizes, and classification information.

The benchmark is intentionally diagnostic: it **does not modify production RVV source** or activate globally regressive packed paths. Neither the exact sparse/dense path taken nor hardware instruction counters are recorded; the crossover measurements provide diagnostic evidence but are not per-instruction proof. A later isolated A/B optimization is justified only after both machines' data are analyzed.

## Validated locally / not yet validated remotely

- Python experiment-generator, corpus and diagnostic/offline tests: PASS.
- C++ Stage 1 / Stage 2 / DOM harness: syntax checked and executed on x86_64 with the archived fork and official 5.0.4 (`fallback` mode). This validates the public/internal API calls and basic timing output format, **not RISC-V performance**.
- Studio UI under a virtual display, with the 102 entry and existing Tests 94–101: PASS.
- **No native Test 102 Cloud-V execution, EPCC Slurm submission or RISC-V compilation has been carried out here.** Watch the first actual build and native preflight before leaving an overnight job unattended.

## If a launch fails

Go to **Tests → 102 → Refresh**, download the diagnostic archive when offered and send `test102_results.zip` plus (if necessary) `studio102-cloudv.log` or `slurm102-<job>.err`. Do not repeatedly click Run on an unconfirmed campaign. Read-only SSH examples:

```bash
# Cloud-V, list latest Test102 folders and statuses
ls -lt ~/rvvlab-v5/test102-cloudv-runs/ | head
find ~/rvvlab-v5/test102-cloudv-runs -name status102.json -print | tail -n 5

# EPCC, verify the real Slurm job state
squeue -u "$USER" -o '%.12i %.18j %.12T %.12M %.12l %.24R'
```

**Test 102 is optimized to find the next optimization target, not to assume the next optimization already exists.**
