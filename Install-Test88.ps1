# Install RVV-VLA Lab Test 88 into an existing Lab checkout (no SSH run).
# ZIP must be extracted to an independent folder before running this script.
param(
  [Parameter(Mandatory=$true)][string]$RepoPath,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$src = (Resolve-Path -LiteralPath $PSScriptRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $src 'experiments\workers\88_prequal_exploration_8h_worker.py') -PathType Leaf)) {
  throw 'Test 88 overlay files missing. Extract ZIP into its own staging folder.'
}
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
foreach ($needed in @('engine\src\simdjson.cpp','studio\RVV_Lab_Studio.pyw','tools\rvvlab.py')) {
  if (-not (Test-Path -LiteralPath (Join-Path $repo $needed) -PathType Leaf)) {throw "Not a complete Lab checkout: $needed"}
}
$paths = @(
 'docs\EXPLORATORY_PREQUALIFICATION_8H.md',
 'experiments\workers\88_prequal_exploration_8h_worker.py',
 'experiments\profiles\88_prequal_exploration_8h.test.json',
 'studio\test_scripts\88_prequal_exploration_8h_worker.py',
 'studio\test_scripts\88_prequal_exploration_8h.test.json',
 'studio\test_scripts\88_prequal_exploration_8h.py',
 'studio\rvvlab_backend.py',
 'studio\RVV_Lab_Studio.pyw',
 'orchestrator\rvvlab_backend.py',
 'tools\rvvlab.py',
 'tools\check_ssh_env.py',
 'tools\verify_release.py',
 'tools\test_prequal_88.py',
 'RUN_TEST_88.bat'
)
$changes = New-Object 'System.Collections.Generic.List[string]'
foreach ($relative in $paths) {
  $source = Join-Path $src $relative
  $target = Join-Path $repo $relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {throw "Missing overlay file: $relative"}
  $different = $true
  if (Test-Path -LiteralPath $target -PathType Leaf) {
    $different = ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne
                  (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash)
  }
  if ($different) {[void]$changes.Add($relative)}
}
Write-Host "Lab root: $repo"
Write-Host "Overlay changes: $($changes.Count)" -ForegroundColor Cyan
$changes | ForEach-Object {Write-Host "  $_"}
if ($DryRun) {Write-Host 'DryRun: no files modified.';exit 0}
if ($changes.Count -eq 0) {Write-Host 'Already installed.';exit 0}
$answer=Read-Host 'Install Test 88 into this Lab checkout? [y/N]'
if ($answer -notmatch '^(?i:y|yes|o|oui)$') {Write-Host 'Cancelled.';exit 1}
# Keep old files OUTSIDE the Git checkout so `git add -A` cannot publish them.
$backupRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'RVV-VLA-Labackups' } else { Join-Path $env:TEMP 'RVV-VLA-Lab-backups' }
$backup=Join-Path $backupRoot ('test88-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($relative in $changes) {
  $source=Join-Path $src $relative
  $target=Join-Path $repo $relative
  if (Test-Path -LiteralPath $target -PathType Leaf) {
    $saved=Join-Path $backup $relative
    New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $target -Destination $saved -Force
  }
  New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
  Copy-Item -LiteralPath $source -Destination $target -Force
  if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne
      (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) {throw "SHA256 copy mismatch: $relative"}
}
Write-Host 'Installed Test 88; external .env and historical results unchanged.' -ForegroundColor Green
Write-Host "Backup (replaced files): $backup"
Write-Host "Verify: py -3 `"$repo\tools\test_prequal_88.py`""
Write-Host 'Nothing has been executed remotely.'
