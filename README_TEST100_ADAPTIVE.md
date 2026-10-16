# VLA-MethodLab — Test 100: adaptive performance campaign

## Installation (DROP ROOT)

1. Close Cloud-V and EPCC Studio instances. Make a backup of `studio/` and `tools/`.
2. Extract this ZIP directly into `C:\mycode\Simdjson\VLA-MethodLab\` and merge directories.
3. Relaunch Studio, select EPCC or Cloud-V, connect SSH.
4. In **JSON Corpus > Performance**, verify that the pinned 18 files are prepared and synced on the selected machine.
5. In **Tests**, click **100**, then **Refresh**, then **Run** once.
6. Wait for native validation and a true server status (EPCC Slurm job ID or Cloud-V detached worker).
7. After completion, download the SHA-256 checked `test100_results.zip`. If the test fails, download the diagnostic ZIP from the same Tests view.

**This patch does not modify the engine or any earlier Test 94–99 source, results, or corpus files.** The patch is based on the Test99 Studio release plus the elapsed-time display changes. The Test 100 profile has a separate run directory and does not silently rerun Test 99.

## Rationale

- Test 99 compiled successfully on EPCC but exited with `Corpus commit mismatch` before any measurement. The script used `4197c425e857f0ec38e89922fdd0bd9ea21f4daf`, while the shared corpus manager uses `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`. Test100 uses the verified latter revision.
- The Test99 official 5.0.3 and 5.0.4 EPCC binaries were SHA-256 identical, so Test100 retains official v5.0.4 as the reference instead of wasting rounds on an identical binary.
- Test97 saw benefits in synthetic boundary cases but less persuasive gains on large public JSON files. Test100 measures **18 public originals** and **57 labeled synthetic exact-boundary files** as **separate** strata.

## Measurements and stopping

- Five variants: official simdjson v5.0.4 (`fallback`), A2 at 4096 (`A2_REF`), 7168, 8192, and 10240 bytes (`rvv`), all built `-O3` with packed disabled.
- Full public files, including their SHA-256, are reused unchanged from the shared performance corpus.
- Synthetic stress: 3 deterministic structural/string families times 19 exact byte lengths between 3584 and 16384. These are **not** presented as real-world input.
- Native `check` validates each file across every executable before timing; all 18 public documents and synthetic inputs must pass. Benchmarks are DOM-only. The sources use the simdjson public API; `fallback` and `rvv` are **different backends**.
- Randomize document/variant order; measure A2 reference before and after each group; CPU affinity is pinned where available.
- Calibrate iterations to ~35 ms per timing replicate; five inner C++ timing repetitions per executable call.
- Adaptive schedule: minimum 45 minutes, at least 8 full rounds and an additional 20-minute confirmation period. Early stop requires **two successive complete rounds** with approximate 95% half-width <= 1% in all three A2 candidate ratios **in both strata**, plus acceptable drift. Otherwise continue up to 4h; EPCC requests a 5h Slurm allocation to cover validation and safety margin. These are safety bounds, not a compulsory fixed 8h runtime.
- Repeated timing rounds are **not** independent held-out documents; report public and synthetic geomeans separately. No automatic engine promotion.

## Preflight / failure handling

- **Before compilation and Slurm:** remote Python validates the pinned upstream commit, the exact list of 18 public fixtures and every file's byte count / SHA-256. A preflight error prevents the job submission.
- **Before native timing:** RISC-V machine and executable SHA-256 checked, then DOM checks; any mismatch fails early.
- Build, preflight, native run and Slurm scripts retain status files; no unconditional deletion of `status100.json`.
- Failures produce `state=failed` and a SHA-256 checked diagnostic ZIP, even when zero performance rows exist. Standard success requires `completed`, `validated=true`, rows > 0 and a valid ZIP.
- Cloud-V prevents launch while other Test94–100 native Python processes appear active. EPCC checks running jobs on `rvc02` and uses a `flock` lock per Test100 worker. Studio also checks remote state before launching, and two Test100 runs cannot overlap.
- If a completed or failed run already exists, the Test100 manifest requests a **new unique run** only after manual Run approval. This does not change previous runs.

## Output

Cloud-V: `~/rvvlab-v5/test100-cloudv-runs/test100-<timestamp>-<suffix>/`.
EPCC: `~/rvvlab-v5/test100-epcc-runs/test100-<timestamp>-<suffix>/`.

Successful ZIP contains `results100.csv`, `summary100.json`, `REPORT_100.md`, `status100.json`, `builds100.json`, `machine100.json`, `corpus_manifest100.json`, `inputs100.json`. Failure archives may contain only a subset; **they are diagnostics, not performance results**.

## Caveats

- Only offline Python checks and a graphical simulated Studio integration were run during preparation. RISC-V compilation, runtime correctness, EPCC queue/walltime limits and SFTP must still be verified on the target machines.
- Confirmation rounds reuse the same input bytes. The public fixture set is small and is not guaranteed representative of any particular production workload.
- A confidence interval computed from repeated rounds does not protect against systematic thermal or workload bias; use the drift diagnostics and independent cross-machine repetition before promoting a new dispatch threshold.
- For detailed Test99 findings, see `ANALYSE_TEST99_ET_PLAN_TEST100.md` (also included in this package).
