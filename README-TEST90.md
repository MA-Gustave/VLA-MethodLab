# RVV-VLA Lab — Test 90 targeted independent holdout (2 hours)

Install into your **existing** Lab (do not extract the full repo on top of your Git repository unless you intend to replace it):

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
$zip = "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Test90_Holdout_2h_Overlay.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $repo -Force
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_holdout_90.py" --full
```

Recommended launch: double-click `LAUNCH_RVV_VLA_LAB.bat`, select **Test Runner -> Refresh -> Adaptive Validation 90 -> Run selected**, then approve. This **does not** start unless manually confirmed.

Alternative root launcher `RUN_TEST_90.bat`, or `python tools/rvvlab.py run holdout-2h --wait`.

**Never start Test 90 while Test 89 or another remote campaign is running.** The worker has a remote global lock and disk safety stop.

A completed run produces `VALIDATION_2H.md` inside the SHA256-verified remote result snapshot. Use the Studio `Sync results` action after completion. When the ZIP is on Windows, upload the evidence ZIP to ChatGPT to interpret. Do NOT upload private SSH `.env`, key files, or complete unredacted remote paths.

This is a 2-hour native-worker budget including builds and validation. Local source packaging and SSH upload happen before remote countdown. None of the Test90 performance measurements were executed when this archive was prepared. Test89 evidence is NOT embedded in this source overlay.
