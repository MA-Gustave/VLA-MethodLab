# RVV-VLA-Lab — disk safety policy (v5.1)

Applies to Lab CLI, integrated Studio, profiles **81–89**, and the legacy Night Runner.
No SSH credentials, `.env`, source tree or historical results are changed.

## New policy

- **200 MiB available** is the absolute free-space floor on the filesystem containing the remote run. An unknown disk reading at local SSH preflight is a **warning**, not an automatic denial: the remote native worker checks again on the Linux host.
- **Below 200 MiB**: do not begin a new run. During a run, trigger a **graceful `safety_stop`**, preserving completed observations, status/checkpoint files, logs and a best-effort snapshot. No deletion/cleanup of other campaigns is attempted.
- **Every 15 minutes (900 seconds)**: record an audit of available space in the worker's status/metadata (`disk_last_15m_check_utc`, `disk_monitor_15m`). **Additional protection is more frequent**: before work steps and during native subprocesses (~0.3–2 s) because a compiler can exhaust disk well before a 15-minute timer expires. This is stricter and safer than checks every 15 minutes only.
- The existing **2 GiB cap on an individual run's workspace** remains; it is independent of free disk space. Under heavy filesystem pressure even best-effort checkpoint writes may fail; 200 MiB is a safety margin, not a guarantee against external disk consumption.
- The runtime budget, benchmark iteration cap, six Test 89 configurations, fixed corpus and SSH source provenance are unchanged.
- Already-running detached campaigns keep their previous uploaded worker and are **not** altered by the local overlay. The policy applies to newly launched campaigns.

## Install (Windows)

Extract `RVV-VLA-Lab_Disk_Safety_200MiB_Overlay.zip` **into the root of your existing** `C:\mycode\Simdjson\RVV-VLA-Lab`, preserving paths and replacing the listed scripts. This overlay does not touch your external `C:\mycode\Simdjson\.env`.

In Windows PowerShell:

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
$zip = "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Disk_Safety_200MiB_Overlay.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $repo -Force
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_disk_safety_200m.py"
& "$repo\RUN_TEST_89.bat"
```

No remote run is started by the offline test. `RUN_TEST_89.bat` requires explicit user approval before SSH deployment.

## Outcomes

A disk-triggered remote stop is marked `safety_stop`, with `stop_reason` and the available disk reading. This is **not** a successful completed benchmark; `map.csv` may contain partial observations and must be interpreted accordingly. Use CLI `status`/`sync` or the integrated Studio to retrieve results after the run. **Do not purge past runs or snapshots** to work around a start check.

## Verification

`python tools/test_disk_safety_200m.py` checks 3.9 GiB launch acceptance; boundary 200/199 MiB; scheduled audit cadence; safe-stop snapshot; CLI handling; nine paired worker copies/manifest SHA256. `python tools/test_prequal_89.py` verifies native smoke **specification and iteration cap** (not execution on RISC-V). Real SSH/Windows/RVV behavior remains to be validated on the server.
