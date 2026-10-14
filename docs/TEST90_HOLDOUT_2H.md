# Test 90 — Independent Holdout Validation (2 hours)

This is a **manual** native 2h RISC-V test designed from Test 89 hypotheses. It is not a source-code optimization and does not claim a new achieved speedup.

**Predeclared hypotheses:** H1: small-input A1/A0 overhead around 512 bytes (NOT a dispatch threshold); H2: A1/A0 and A2/A0 discontinuity at the actual 4096-byte dispatch gate; H3: A2 vs sparse8 on dense+numbers+UTF8, dense+escaped/Unicode and similar mixes; H4: complex features after the first 512B or 4096B; H5: Stage1 versus Stage2 source of gain.

**Backends:** official upstream v5.0.3 `rvv_vls256`, `A0_E14_original`, `A1_size_gate`, `A2_quick_dispatch`, `sparse8_escape8_reference`. These are independently compiled profiles, **not runtime switching**.

**Important:** The size gate is **4096 bytes**; **512 bytes** is the quick classifier inspection window on larger inputs, not a dispatch threshold for small inputs. The benchmark also changes iterations between 512 and 513 bytes; interpret that size boundary cautiously.

**Workload:** entirely new seed `20261013`, exact gate lengths and true multi-family deceptive documents, unique SHA256 per JSON, no duplication with prior campaign generator seed. The new corpus is *not* selected based on live performance. The priority block has 88 fixed, stratified scenarios and is run for 3 independent subprocess trials per case (15 per case across five backends), before secondary coverage.

**Timing/safety:** 2 hours on the remote worker, inclusive of native compilation and correctness/split smoke. Windows source snapshot preparation and SSH deployment happen beforehand; 1–1000 benchmark iterations; mandatory 256B and 4095/4096/4097B native smokes for every backend; no fallback to fewer than five backends. Native free disk <200 MiB triggers `safety_stop`; monitoring every 15 min and during disk-heavy commands. Global remote campaign lock. Stop by Studio; no automatic deletion, no SSH credentials packaged.

**Results:** `map.csv`, `prequal_pairwise.csv`, `ranking.csv`, `corpus_manifest.json` with SHA256, `VALIDATION_2H.md` grouped descriptive case-level geometric means and approximate bootstrap bounds, `status.json`, `checkpoint.json`, `metadata.json`, trend/coverage CSVs; SHA256-verified snapshot sync. The bootstrap treats each JSON as a unit, not repeated trials as independent documents. No cross-device inference or blanket performance guarantee.

**One-click:** root `RUN_TEST_90.bat`. **Preferred:** integrated Lab Studio → Test Runner → Refresh → select Test 90 → Run selected. **CLI:** `python tools/rvvlab.py run holdout-2h --wait`. Do not run more than one campaign simultaneously.

No remote execution was performed while preparing this release. Run `python tools/test_holdout_90.py --full` to reconstruct and check the entire holdout locally before execution. Avoid putting your external `.env` on GitHub.
