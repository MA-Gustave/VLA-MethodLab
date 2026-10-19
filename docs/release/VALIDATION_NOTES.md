# Validation notes — reconstructed clean MethodLab repository

All source material came from the uploaded `wholeRepo.zip` (2026-10-18); the historical engine source was not changed. The new package is a *full clean installation*, not an overlay.

## Checks completed on the rebuilt tree

- ZIP source integrity: PASS.
- Both root transport archives `results.zip` and `logs-reports.zip` exactly matched the corresponding extracted files prior to deduplication.
- The 15 files in `logs-reports/106-cloudv/` exactly matched the archived Cloud-V Test106 result ZIP.
- All 10 native benchmark ZIPs (Tests 101, 102, 103, 104, 106) were preserved byte-for-byte. Digests are in `NATIVE_ARCHIVE_DIGESTS.json`. No Test105 native archive was provided in `wholeRepo.zip`.
- Historical `results/runs/` remained at the exact same paths with unchanged content.
- Main Studio unittest suite: **67 tests passed** under a virtual X display; this is the suite in `studio/tests/`.
- Test107 auditor ran directly against the two unmodified native Test106 result archives: **167,835 measurements, ENGINE PASS / RELEASE HOLD**.
- Whole-release SHA-256 inventory is regenerated and can be checked with `python tools/verify_release_tree.py`.

## Legacy test limitation

An indiscriminate `unittest discover` over the old `tools/` directory does **not** pass: some historic command-line scripts parse arguments at import time, while other scripts assert pre-Test107 interfaces, language labels or ordering. This is not a passing CI/safety result and should not be described as one. The clean package leaves those historical scripts and the C++ engine unchanged so past experiments remain reproducible.

## Remaining release condition

The GitHub Actions #74 fuzz/Valgrind workflow failed. The exact failing step has not been independently confirmed from this archive. The Test107 result qualifies existing native performance evidence but **does not certify the release CI**.
