# CLI wizard entry point. Uses the same isolated .venv and dependency checker.
# Does not install packages or connect to SSH without explicit user action.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$check = Join-Path $root 'studio\check_runtime.py'
$req = Join-Path $root 'orchestrator\requirements.txt'
if (-not (Test-Path -LiteralPath $check)) { throw 'Missing studio/check_runtime.py. Apply the launcher fix.' }
if (-not (Test-Path -LiteralPath $python)) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $creation = Start-Process -FilePath $py.Source -ArgumentList @('-3', '-m', 'venv', ('"'+$venv+'"')) -Wait -NoNewWindow -PassThru
    } else {
        $py = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $py) { throw 'Python 3.10+ is required.' }
        $creation = Start-Process -FilePath $py.Source -ArgumentList @('-m', 'venv', ('"'+$venv+'"')) -Wait -NoNewWindow -PassThru
    }
    if ($creation.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $python)) { throw 'Local Python .venv creation failed.' }
}
$probe = Start-Process -FilePath $python -ArgumentList @(('"'+$check+'"'), 'paramiko') -Wait -NoNewWindow -PassThru
if ($probe.ExitCode -ne 0) {
    $answer = Read-Host 'Install Paramiko in local .venv? [Y/n]'
    if ($answer -and $answer -notmatch '^(?i:y|yes|o|oui)$') { throw 'Installation declined.' }
    $install = Start-Process -FilePath $python -ArgumentList @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', ('"'+$req+'"')) -Wait -NoNewWindow -PassThru
    if ($install.ExitCode -ne 0) { throw 'Paramiko installation failed.' }
}
$probe = Start-Process -FilePath $python -ArgumentList @(('"'+$check+'"'), 'paramiko') -Wait -NoNewWindow -PassThru
if ($probe.ExitCode -ne 0) { throw 'Paramiko import failed.' }
$wizard = Join-Path $root 'tools\rvvlab.py'
if (-not (Test-Path -LiteralPath $wizard)) { throw 'Missing tools/rvvlab.py' }
& $python $wizard wizard
if ($LASTEXITCODE -ne 0) { throw 'RVV-VLA Lab CLI wizard failed.' }
