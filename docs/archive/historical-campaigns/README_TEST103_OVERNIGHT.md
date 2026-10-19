# Test 103 — Stage 2 Escape Decoder Optimization (Cloud-V + EPCC)

Test 103 **changes C++ Stage 2 code in compile-only experimental variants**. It is **not** another threshold sweep, and **not** a production patch to the fork. All candidate binaries are built from the same sha256-pinned RVV fork as Tests 101/102. The production source tree and the Test 102 campaign remain unchanged.

## What it compares

| Variant | Description |
|---|---|
| `OFFICIAL_504` | Official simdjson v5.0.4, fallback backend (context, **not same-backend A/B**) |
| `A2_G16384` | **Unchanged RVV A2** with 16 KiB threshold (main scientific reference) |
| `A2_SIMPLE_RUN` | Experimental Stage 2 modification: decode consecutive simple JSON escapes without returning to the quote/backslash SIMD scanner after every pair |
| `A2_NL4` | Same modification plus a four-pair `\n` burst fast path, compared against the original **and** SIMPLE_RUN |

The patch inserts code only in the normal `parse_string()` decoder. It guards against unknown input header versions with an exact SHA-256 and never writes into the deployed fork checkout: build variants use a separate header overlay in the run directory. Unicode `\uXXXX` stays with the original decoder. Invalid escapes are still checked by the original path. The escaped-string path still undergoes native correctness checks before benchmarking.

**Performance expectations are hypotheses, not results.** The Test 102 results pointed to Stage 2 as the main pathological dense-escape bottleneck, but it is not yet known whether these two code changes are beneficial on either real RISC-V machine.

## Workloads and experimental design

- **18 public JSON** from the pinned `simdjson-data` corpus, unchanged and checked by hash.
- **206 deterministic synthetic probes in exploration** and **206 independently seeded probes in confirmation**: controlled backslash density 0/1/3/6/10/15/25/50%, escape type, 4/8/16 KiB sizes, and 8-to-9 backslash crossover.
- DOM parse throughput, actual Stage 1 throughput, actual Stage 2 throughput recorded separately; do **not** add Stage timings or merge the public and synthetic strata.
- Randomized candidate order and before/after unchanged A2 anchor; complete paired rows only; SHA-256 per input and per executable.
- Exploratory **4 h**, confirmation **2 h 30**, total **6 h 30 max** for the worker; EPCC Slurm allocation **7 h 30**. Source deployment, compilation and Slurm queueing add time.
- ZIP, CSV, JSON summaries, failure diagnostics; idle or failed remote runs are never silently labeled successful. Separate EPCC and Cloud-V evidence.

## Install — one DROP ROOT ZIP, no installer

1. Ensure there is no active **local** source deployment; close both Studio windows. Existing confirmed remote jobs are independent and not stopped by closing Studio.
2. Back up `studio/` and `tools/`. Extract the ZIP directly inside `C:\mycode\Simdjson\VLA-MethodLab\` and accept file replacements.
3. Open Studio in its separate **EPCC** and **Cloud-V** windows; connect SSH.
4. In **JSON Corpus → Performance**, verify the PC has the **18** public JSON files. Test 103 syncs and SHA-checks them on each server before compilation.
5. In **Tests → 103**, click **Refresh → Run**, **once per machine**. Avoid other CPU benchmarks on the same machine.
6. On **EPCC**, wait for an actual **Slurm Job ID**; on Cloud-V, wait for a confirmed detached process. Once submitted, Windows and Studio can be closed.
7. After completion (or any failure), use **Download** to retrieve the SHA-256-checked `test103_results.zip` archives. Send both to analyze paired A2 speedups.

The tests do not launch automatically when the ZIP is extracted. They require a deliberate **Run** click. Anti-duplicate checks are retained; test 102 stays available in Studio.

## Primary question

Does `A2_SIMPLE_RUN` or `A2_NL4` improve **Stage 2 and full DOM throughput** on high-escape-density workloads on **both** EPCC and Cloud-V, without measurable regression on **public JSON**? The A2 16-KiB reference remains unchanged throughout.

## Local verification and remaining uncertainties

- The modified generic Stage 2 header was compiled on **x86_64** using the pinned fork. Three differently hashed binaries (unchanged / simple run / NL4) produced **identical canonical DOM output** on ten purpose-built cases including Unicode, mixed escapes, and long repetitions.
- Offline tests include corpus/hash rejection, all 412 generated JSON validity and exact sizes, digest-pinned overlay, failure ZIP handling, and schema of summary comparisons. Studio UI tests cover the new entry and coexistence of Tests 102 and 103.
- **No native RISC-V compilation or EPCC Slurm run has been performed here**; actual native correctness and performance remain to be verified on the servers. A native failure should produce a diagnostic ZIP. Do not assume an optimization works until this has passed.

Cloud-V read-only check: `find ~/rvvlab-v5/test103-cloudv-runs -name status103.json -print 2>/dev/null`.
EPCC read-only check: `squeue -u "$USER" -o '%.12i %.18j %.12T %.12M %.12l %.24R'`.
