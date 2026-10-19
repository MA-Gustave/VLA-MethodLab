# Test 93 — Stage 1 / Packed-Build Overhead Isolation (3h maximum)

**Purpose:** Diagnostic follow-up to Test 92, **not** another 242-point search. Test 92 selected static compositions that lost roughly 24–25% full-DOM throughput against the dedicated A2 baseline, even though they frequently exceeded the official VLS256 build. `policy=0` in the instrumented research build also lost substantially to A2. **Test 93 isolates confounded costs more carefully.**

## Fixed, four-way measurement design

Four independent RVV native builds (compilation time is **inside** the 3-hour budget):

| Executable / setting | Compile-time definition and purpose |
|---|---|
| `A2` | Dedicated A2 baseline; packed flags disabled; **100% throughput reference** |
| `official` | Official upstream VLS256; secondary reference |
| `packed_plain` | Packed control + packed index writer enabled, **no experimental runtime explorer** (`SIMDJSON_RVV_EXPLORATION91=0`) |
| `compositions` | Research implementation with `SIMDJSON_RVV_EXPLORATION91=1`, run under the selected native policy |

This controls two separate comparisons: `packed_plain / A2` is the packed-build delta, and research `policy=0 / packed_plain` approximates additional research-path overhead. It is **not** a perfectly causal instruction-level ablation; compiler code generation and runtime paths differ, and CPU noise remains.

Nine **precommitted** compositions from the successful Test 92 run are tested (no adaptive winner selection):

| Point | Category |
|---|---|
| `P7042b142196b` | `policy=0` overhead-control baseline |
| `P17f43a9d4f1d` | `policy=1` neutral static comparison |
| `P2345c07522b1` | Test 92 holdout winner, static |
| `P6f95844a1fa9` | Test 92 holdout second, static |
| `Pe991d1cf900e` | Test 92 holdout third, static |
| `Pf7e94cfcb820` | `policy=2` prefix-classified |
| `Pf9f644d6d8a0` | `policy=3`, regional switching observed in Test 92 |
| `P638c6d2cc96b` | `policy=3`, regional switching observed in Test 92 |
| `Pea0c21bc7f78` | `policy=4`, sampled-selector comparison |

Twelve shared stress anchors cover ASCII, dense, escaped, UTF-8, long strings, Unicode escapes, nesting, floats, many keys, and regioned layouts, at **64 KiB, 1 MiB or 8 MiB**. 64 MiB is intentionally excluded from this short diagnostic experiment. The campaign repeats anchors until 80% of the **post-build** time is exhausted, then freezes all non-rejected candidates and runs fresh-seed holdout on a shared rotating set until the absolute three-hour deadline.

Every timed group uses **the same JSON bytes and iterations** for A2, official, `packed_plain`, and the current research composition, **with randomized measurement order**. Both experimental and `packed_plain` binaries pass untimed full-DOM agreement against fallback. Native valid/invalid JSON correctness checks, SHA256 snapshot verification, process-group termination, 200 MiB free-disk floor, 2 GiB campaign cap, remote exclusive lock, and manual launch from Studio are preserved.

## Launch

1. Back up your project or use the complete release archive. Close Studio. Extract the Test 93 update archive into the `RVV-VLA-Lab` directory (or extract the complete archive into its parent).
2. Start Studio and click **Refresh** in Test Runner. Select **Test 93 — Stage1/overhead isolation (3h max)** and click **Run selected**. This profile is **manual-only** and is not added to the run queue.
3. Wait for the detached RISC-V run, then **Sync results**. Closing Studio does not kill the remote experiment.

Optional CLI after an explicit confirmation:

```powershell
.\.venv\Scripts\python.exe tools\test_exploration_93.py
.\.venv\Scripts\python.exe tools\rvvlab.py run diagnose-93-3h --wait
```

Or double-click `RUN_TEST_93_3H.bat` (runs portable verification, then asks Y/N before remote start).

**Result packet:** `EXPLORATION_93.md` includes matched full-DOM/Stage1/Stage2 throughput ratios **and signed percentage differences relative to A2**, separated by training and fresh-seed holdout. `map.csv` contains three observations per group (research, A2, official); `controls93.csv` contains the fourth, `packed_plain`; match by `group` for four-way metrics. `diagnostics.csv` records regional counters. `metadata.json`, `build_provenance.json`, `snapshot.sha256`, `MANIFEST.json` preserve provenance/integrity. **Do not compare raw aggregate GB/s across different groups.**

## Caveats and validation status

- The experiment is **not executed remotely** by preparing or installing this archive. It still requires native RISC-V compilation and validity checks on the user's server.
- The absolute three-hour limit **includes builds, native smoke and correctness**, not snapshot upload and Windows result download; SSH deployment can take extra time.
- **No target throughput uplift is promised**. The objective is attribution/diagnosis, not production promotion.
- Complete four-way groups are required to interpret ratios; a partial last group is excluded.
- The Test 92 performance report in English is at [`docs/results/2026-10-13-test92-performance-report.md`](docs/results/2026-10-13-test92-performance-report.md).

Portable preflight:

```powershell
.\.venv\Scripts\python.exe tools\test_exploration_91.py
.\.venv\Scripts\python.exe tools\test_exploration_92.py
.\.venv\Scripts\python.exe tools\test_exploration_93.py
.\.venv\Scripts\python.exe tools\verify_release.py --hashes
```
