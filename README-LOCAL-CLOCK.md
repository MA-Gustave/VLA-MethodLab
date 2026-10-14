# Local clock for RVV-VLA Lab Studio (Test 90 compatible)

## What changed

The header displays an updating clock every second:

    PC  15:04:34 (UTC-04:00)   |   UTC  19:04:34

PC is the local timezone configured in Windows. It uses the correct UTC offset
for the date, including daylight-saving time. This clock is independent of SSH.

Under **Test Runner > RVV Lab campaigns**, **Last update (PC)** converts the
UTC timestamp returned by the RISC-V server into the PC's local time, including
an explicit UTC offset. Remote records, `status.json`, benchmark timestamps,
SHA256-verified evidence and the `night-...Z` campaign IDs stay in UTC.

## Install into an existing Lab

Close Studio first. Extract the overlay ZIP into the Lab root, overwriting
existing files. In PowerShell:

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
$zip = "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Studio_Local_Clock_Overlay.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $repo -Force
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_studio_clock.py"
& "$repo\LAUNCH_RVV_VLA_LAB.bat"
```

No engine, SSH credentials, `.env`, remote workers, measurements, or campaigns
are modified. No remote run is started.
