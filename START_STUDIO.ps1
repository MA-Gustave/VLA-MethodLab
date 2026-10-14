# Alternative PowerShell entry point. Delegates to the maintained BAT launcher.
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'LAUNCH_RVV_VLA_LAB.bat'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw ('Missing launcher: ' + $launcher)
}
# cmd.exe runs BAT files without Powershell's native-stderr error translation.
$command = '"' + $launcher + '"'
& cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { throw 'RVV-VLA Lab Studio launcher returned an error.' }
