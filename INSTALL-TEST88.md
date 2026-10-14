# Test 88 — quick installation into existing RVV-VLA Lab

1. Extract `RVV-VLA-Lab_Test88_8h_Combinatorial_Overlay.zip` to a **temporary folder**, not directly into the Lab.
2. Run the installer after inspecting the changes:

```powershell
$stage = "$env:USERPROFILE\Downloads\RVV-Test88"
$repo = "C:\mycode\Simdjson\RVV-VLA-Lab"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Test88_8h_Combinatorial_Overlay.zip" -DestinationPath $stage -Force
pwsh -NoProfile -File "$stage\Install-Test88.ps1" -RepoPath $repo -DryRun
pwsh -NoProfile -File "$stage\Install-Test88.ps1" -RepoPath $repo
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_prequal_88.py"
& "$repo\.venv\Scripts\python.exe" "$repo\tools\verify_release.py"
```

The installer backs up replaced files under the Windows `%LOCALAPPDATA%\RVV-VLA-Labackups` directory **outside Git**; it does not touch `.env`, `.git`, or `results/`. It includes the v6 external `.env` bridge, so your credentials can stay in `C:\mycode\Simdjson\.env`. **No campaign launches during installation.**

Launch by opening integrated Studio → Test Runner → Refresh → **Test 88**, or via the Lab root:

```powershell
& "$repo\RUN_TEST_88.bat"
# CLI alternative:
python "$repo\tools\rvvlab.py" run prequal-8h --wait
```

The SSH worker uses a total 8-hour budget, a global process lock, grace-stop file, checkpoints and SHA256-verified evidence snapshots. **Run 87 and Test 88 are independent**; Test 87's results, when available, remain untouched.

Only native riscv64 can benchmark the campaign. The local validation tests its corpus generator, manifest SHA256, standard-library parsing and data-processing code. Do not claim an 8-hour performance result until the remote run is completed and the evidence is synced.
