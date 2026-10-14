# Legacy Studio entry point; keep the entry point but use a single BAT path.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Path $PSScriptRoot -Parent
$launcher = Join-Path $root 'LAUNCH_RVV_VLA_LAB.bat'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw ('Missing root launcher: ' + $launcher)
}
$command = '"' + $launcher + '"'
& cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { throw 'RVV-VLA Lab Studio launcher returned an error.' }
