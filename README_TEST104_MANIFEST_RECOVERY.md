# Test 104 — Restore missing campaign files (DROP ROOT)

**Cause proven from `znapshot_VLA-MethodLab_10172214.zip`**: the local snapshot contains the Test 104 UI index and refresh hotfix, but neither `studio/test_scripts/104_escape_stage.py` nor `104_escape_stage.test.json` nor the Test104 tools/downloader. EPCC run discovery also lacks a `test104` registry entry. This is a **local incomplete installation**, not a remote Slurm/build failure.

This is a **restoration package** based on the original Test104 distribution, retaining your already installed Test104 Studio-refresh hotfix. It includes all missing Test104 scripts, checked against their original bytes, and an EPCC results registration that preserves the snapshot's other entries.

## Install

1. If anything is currently being uploaded or compiled from Studio, let it reach a confirmed independent remote state; **do not interrupt existing remote jobs**.
2. Close both Studio windows. Optional: back up `studio/` and `tools/`.
3. Unzip this package at **`C:\mycode\Simdjson\VLA-MethodLab\`**, merge directories and accept the replacement of `studio/rvvlab_epcc_results.py`. No extra folder level.
4. Reopen the independent Cloud-V and EPCC Studio windows, connect them, select **Tests → 104**, click **Refresh**, then **Run** on each machine **once**.
5. If `Test manifest missing/disabled` persists, open **Advanced tools → Test Runner** and ensure its **Scripts folder** is exactly `C:\mycode\Simdjson\VLA-MethodLab\studio\test_scripts`; click that page's **Refresh**. Confirm `Test 104 — Independent JSONTestSuite + Stage2 validation` is listed as Ready (manual). Do not launch the test twice.
6. The campaign requires verified **Performance** (18 files) and **Conformance** (official JSONTestSuite) corpora in **JSON Corpus**. Prepare/verify these *before* Run. A missing corpus must fail preflight, not start a partial remote benchmark.

This package does **not** touch the fork's C++ source, remote data, existing Test100–103 runs or previously downloaded results. It does not automatically launch Test104. No remote RISC-V job has been performed in this environment.

## Exact delivered changes

- Restores `studio/test_scripts/104_escape_stage.py` and `104_escape_stage.test.json`.
- Restores `studio/rvvlab_test104_download.py`.
- Restores seven `tools/test104_*` files (native worker, Stage2 patch, split harness, Cloud-V and EPCC launch scripts, EPCC builder, diagnostics).
- Adds `test104` to `studio/rvvlab_epcc_results.py` while leaving the rest of that snapshot file unchanged.
- Includes the original Test104 offline test suite and a new installation/manifest check.

**Do not install the earlier status-only hotfix over this restoration as a substitute for the missing Test104 scripts.** The status-only hotfix does not include the required runner or tools.
