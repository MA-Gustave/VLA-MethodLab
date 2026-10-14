# RVV-VLA Lab — Test 89 remote evidence recovery (no rerun)

## What happened

The completed native run `night-20261012T133100Z-5a6468` reported
`stopped`, 2,453 observations at the one-hour deadline. **The remote run succeeded**
(up to the intended time limit); local result synchronization failed because the
old allowlist recognized `EXPLORATION_8H.md` but not `EXPLORATION_1H.md`.
The worker packages 14 SHA256-listed result files for either format.

## Install

Extract this overlay into `C:\mycode\Simdjson\RVV-VLA-Lab`, with overwrite.
No credentials, `.env`, engine files, historical data, or remote workers are changed.

## Windows recovery (double-click)

`PULL_TEST_89.bat`

The batch script first runs offline regression tests on **both** the CLI and
Studio snapshot verifiers. It then connects to your configured SSH host (using
the existing external `.env`) and downloads the exact remote Test 89 ZIP.
It checks the remote snapshot SHA256 before download is accepted, then validates
the 14 named files individually by SHA256 and expected byte length.
**It never starts the campaign or deletes server files.**

Recovered evidence ZIP:

`results\local\night-20261012T133100Z-5a6468-evidence.zip`

Upload that evidence ZIP to ChatGPT to examine `prequal_pairwise.csv`, `TRENDS.md`,
`coverage_by_design.csv`, `ranking.csv`, `map.csv`, `failures.csv` and `status.json`.
The synced files also appear below `results\local\NightRuns\<run-id>\`.
Please review machine-specific metadata before publication.

### Alternative using Lab Studio

Close/reopen Lab Studio after installing the patch. Connect SSH, open **Night
Explorer / RVV Lab campaigns**, refresh, select
`night-20261012T133100Z-5a6468`, then click **Sync results**.
The Studio will extract the same SHA256-verified snapshot to its configured
results folder. This UI path does not create the one-file evidence ZIP; use
the BAT if you want a convenient upload archive.

### Alternative CLI

```powershell
& 'C:\mycode\Simdjson\RVV-VLA-Lab\.venv\Scripts\python.exe' 'C:\mycode\Simdjson\RVV-VLA-Lab\tools\rvvlab.py' sync night-20261012T133100Z-5a6468
```

## Integrity and research interpretation

The patch adds **one explicit accepted report filename** in both local sync
verifiers. It does not bypass hash checks, raise maximum ZIP size, accept
arbitrary file names, or make a fake remote success claim. `stopped` is a normal
time-budget outcome; full analysis may still reveal missing pairs or failures,
so do not interpret 2,453 observations as 2,453 complete cross-engine pairs.
