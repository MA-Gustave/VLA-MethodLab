> **RIGHTS NOTICE — INDEPENDENT LAB, MIXED ORIGIN, PROSPECTIVE UPSTREAM EXCLUSION**  
> This repository **includes `engine/`**, a simdjson-derived engine under its applicable existing upstream and third-party licences. Neither the lab nor the engine is made wholly proprietary by this notice. For future or otherwise verified, independently controlled and individually registered original additions, **no licence is granted for incorporation into official simdjson without separate signed authorization**. Previous Apache/MIT and other grants cannot be revoked. See [LICENSE](LICENSE), [scope](LICENSE-SCOPE.md), [register](PROVENANCE-ADDITIONS.md), [upstream exclusion](UPSTREAM-EXCLUSION.md).

# VLA-MethodLab — Clean release-candidate repository

This self-contained research laboratory includes a preserved historical engine (`engine/`), two Studio launchers for EPCC and Cloud-V, native benchmark tools and archived evidence. The separate [VectorPath-RVV](https://github.com/MA-Gustave/VectorPath-RVV) repository is the candidate engine for publication; this Lab's historical engine **must not be silently replaced**, to preserve comparisons to earlier experiments.

## Install from scratch (Windows)

1. **Back up your `.git` directory and any local `.env`, SSH keys, `.venv`, local output, and ZmartZnap snapshots.** They are *not* part of the distribution. If you want to keep Git history, clone the repository in a fresh directory first, then extract the distribution there.
2. Extract the entire `VLA-MethodLab_FULL_REPOSITORY_CLEAN_INSTALL_20261018.zip` **into the root of a clean `VLA-MethodLab` folder** (the ZIP contains no extra wrapper directory).
3. Run `LAUNCH_STUDIO_CLOUDV.bat` and/or `LAUNCH_STUDIO_EPCC.bat`, or the corresponding `.pyw` launchers. Python 3.10+ and Paramiko are required for remote connections; the launcher can set up a local `.venv`.
4. Find **Test 107 — LOCAL** in the main Tests view. This is an offline evidence audit; it never starts a new EPCC/Cloud-V campaign.

See [CLEAN_INSTALL_RELEASE.md](CLEAN_INSTALL_RELEASE.md) for complete verification and repository layout.

## What is frozen and what is not

- Test 106 evidence: [DOM performance report](results/releases/test106/TEST106_VectorPath_RVV_Final_Native_Performance_Report_EN.md) and [18-document CSV](results/releases/test106/TEST106_Public_18JSON_PerDocument_Results_EN.csv).
- Test 107: [Formal evidence audit](results/releases/test107/TEST107_FORMAL_RELEASE_AUDIT_EN.md), auditor `tools/test107_release_audit.py`. The audit verifies previous native runs, not a new performance experiment.
- Final performance against **official simdjson v5.0.4 fallback** on the 18 public JSONs: **+60.07% Cloud-V** and **+89.46% EPCC**. Do not mix these values with Test 89's different official backend/corpus.
- `SIMPLE_RUN` and `NL4` are **optional**, not the default release Stage 2 parser.
- **CI fuzzing/Valgrind #74 remains unresolved** (build job exit code 7); no claim of complete CI clearance is made here.

## Layout

- `studio/`: graphical interface, main Tests 94–107 catalogue and local Test107.
- `engine/`: original historical simdjson/RVV lab engine, left unchanged.
- `tools/`, `orchestrator/`, `experiments/`: benchmark, launcher and analysis code.
- `release_candidates/`: pinned VectorPath candidate sources used for Test106/107.
- `results/runs/`: unchanged historical data. `results/releases/test106/`, `results/releases/test107/`: canonical release analysis.
- `logs-reports/raw-native/testNN/`: exact original RISC-V result ZIPs. `logs-reports/reports/`: historical scientific reports, with no standardization yet.
- `docs/reference/`, `docs/archive/`, `docs/release/`: reference, history and release methodology.
- `SHA256SUMS.txt`: regenerated current full-tree checksums (see verification instructions).

## Licensing and provenance

The repository has mixed original and upstream components. Retain `LICENSE`, `NOTICE`, `LICENSE-SCOPE.md`, `PROVENANCE-ADDITIONS.md`, `THIRD_PARTY_LICENSES/`, `licenses/` and the upstream licences in `engine/`. See `UPSTREAM-EXCLUSION.md` for the scope of independent additions.
