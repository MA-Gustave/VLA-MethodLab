@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" goto missing_python
echo.
echo ===== RVV-VLA Lab - Recover Test 89 results =====
echo This operation is read-only on the RISC-V server.
echo No benchmark will start. No remote file will be deleted.
echo.
"%PY%" "%ROOT%tools\test_snapshot_89_sync.py"
if errorlevel 1 goto fail
"%PY%" "%ROOT%tools\rvvlab.py" sync night-20261012T133100Z-5a6468
if errorlevel 1 goto fail
echo.
echo SUCCESS - Upload this file for analysis:
echo "%ROOT%results\local\night-20261012T133100Z-5a6468-evidence.zip"
pause
exit /b 0
:missing_python
echo ERROR - Local .venv Python missing. Open Lab Studio or install Python.
pause
exit /b 2
:fail
echo ERROR - Recovery was not completed. The remote result has NOT been deleted.
pause
exit /b 1
