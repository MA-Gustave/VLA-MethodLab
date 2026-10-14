# Test 89 — corrected 60-minute prequalification pilot

## Why a new ID (89)?

The October 12 native **Test 88 failed with 0 performance observations** after all ten binaries passed JSON correctness. Its C++ `split` benchmark deliberately rejected iteration counts above 1000 (return code 6), while the Python scheduler requested 2048 iterations for JSON <=512 bytes and 1024 for 513..2048 bytes. The official control and all nine RVV variants failed the first 256-byte benchmark. The original log/snapshot is preserved and not reclassified as success.

Test 89 is a **new** precommitted pilot. It changes the iteration schedule, adds a native split smoke for every compiled backend and limits time to **3600 seconds measured from remote worker startup, including native compilation, validation, corpus generation and benchmarking**. It does not mutate the existing Test 88 or the C++ engine tree.

## Precommitted design

* Native RISC-V RVV VLEN256, GCC `-O3`, public simdjson v5.0.3 VLS256 reference pinned to commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249`.
* Six separately compiled engine configurations: upstream_vls256, A0_E14_original, A1_size_gate, A2_quick_dispatch, E01_adaptive and sparse8_escape8_reference.
* 767 deterministic, valid synthetic JSON corpus files in six experiment designs: single (128), pair (352), triple (144), skew (72), exact (51), heavy (20). Approximately 179 MiB synthesized. **This is a candidate library, not a promise to benchmark all 767 cases in one hour.**
* First measurements use an **81-case stratified priority wave**, interleaving six design types and rotating spatial distributions. After this, remaining cases use seeded shuffling with alternated candidate execution order. No runtime change of engine configurations based on observed results.
* Per-case iteration counts are always in 1..1000, including 1000 for 256-512-byte documents, 768 for <=2048 bytes, 512 for <=8192 bytes, and fewer for large files.
* Before any exploratory timing, **every native binary** must pass JSON valid/invalid classification plus actual `split` calls at 256 bytes / **1000 iterations**, 4095, 4096 and 4097 bytes / 32 iterations. Failures are recorded as `native_smoke` in metadata/failures.csv; the two critical baselines cannot be missing.
* Benchmarks measure three medians of separate public DOM parse, internal Stage1 and internal Stage2 wall time; no software extrapolation from DOM. This is one hardware/compiler environment, not independent systems.
* The worker is single-instance under the server's exclusive lock; 2 GiB workspace cap; 200 MiB free-disk guard with 15-minute logged checks and more frequent runtime enforcement; graceful STOP file; 60-minute deadline; periodic SHA256 snapshot; no automatic winner or post-hoc tuning.

## Install only in RVV-VLA-Lab

Unzip the overlay contents **directly into the root directory of your existing Lab**, preserving the directory structure, or extract into a separate temporary directory then copy files. It includes no `.env`, passwords, Git folder, or private identities.

The Lab discovers your existing `C:\mycode\Simdjson\.env` through the previously installed external-ENV bridge. Keep this file private.

For Windows, double-click `RUN_TEST_89.bat` at the Lab root (explicit start confirmation), or select **Test 89** in `LAUNCH_RVV_VLA_LAB.bat` -> GUI Test Runner, or run from Lab root:

```powershell
.\.venv\Scripts\python.exe tools\test_prequal_89.py
.\.venv\Scripts\python.exe tools\rvvlab.py run prequal-fixed-60m --wait
```

The 60-minute budget is **remote**, excluding initial Windows source packaging and SFTP upload. A normal time-budget stop is recorded as `state=stopped` and `stop_reason='1-hour budget reached'`, not `completed`. If compilation consumes most of the hour, insufficient performance observations are possible; the packet will transparently report that.

## Retrieval and interpretation

If you closed the Studio window, retrieve later with:

```powershell
.\.venv\Scripts\python.exe tools\rvvlab.py status
.\.venv\Scripts\python.exe tools\rvvlab.py sync night-YYYYMMDDTHHMMSSZ-xxxxxx
```

All 14 snapshot files are allowed by the included audited sync patch; SHA256 verification remains required. Results include `status.json`, `map.csv`, `failures.csv`, `metadata.json`, `TRENDS.md`, `prequal_pairwise.csv`, `coverage_by_design.csv`, `hypotheses_to_confirm.csv`, `EXPLORATION_1H.md` and additional supporting files. **Compare paired runs only** (same corpus, phase, trial, iteration count); no significance, stable winner, or multi-hardware generalization can be claimed from this pilot. Send the result packet to the assistant for interpretation before scheduling the confirmatory 8-hour campaign.

## Offline preflight

```powershell
.\.venv\Scripts\python.exe tools\test_prequal_89.py
# optional thorough test: regenerates ~179 MiB in a temporary folder
.\.venv\Scripts\python.exe tools\test_prequal_89.py --full
.\.venv\Scripts\python.exe tools\test_snapshot_88_sync.py
.\.venv\Scripts\python.exe tools\verify_release.py
```

All these checks are offline; native GCC/RVV execution must be verified on your RISC-V server.

## Disk safety patch v5.1 (after initial insufficient-space rejection)

The original 4 GiB launch, ~3.6 GiB build, and 3 GiB runtime guards were Lab-specific arbitrary thresholds. The updated policy uses a 200 MiB **safety stop** for newly launched runs, a logged status/metadata disk check at least every 15 minutes during an active worker, and more frequent checks before new work and while compilers execute. `safety_stop` is terminal, retrievable, and not equivalent to successful completion. For installation and offline tests see `README-DISK-SAFETY.md`. Existing uploaded workers are not changed.
