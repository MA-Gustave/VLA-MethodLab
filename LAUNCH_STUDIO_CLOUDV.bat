@echo off
setlocal EnableExtensions DisableDelayedExpansion
REM Dedicated Studio: Cloud-V. Other machine window stays open.
set "RVVLAB_STUDIO_TARGET=Cloud-V"
if not exist "%~dp0LAUNCH_RVV_VLA_LAB.bat" goto missing_launcher
call "%~dp0LAUNCH_RVV_VLA_LAB.bat"
exit /b %errorlevel%
:missing_launcher
echo ERROR: LAUNCH_RVV_VLA_LAB.bat is missing from this folder.
pause
exit /b 1
