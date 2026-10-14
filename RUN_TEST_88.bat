@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
echo.
echo ===== RVV-VLA Lab ^| Test 88 ^| Exploratory 8 Hours =====
echo.
if not exist "%PY%" goto missing_python
echo Checking Test 88 code and manifests locally...
"%PY%" tools\test_prequal_88.py
if errorlevel 1 goto failed
echo.
echo This will start an 8-hour native campaign on YOUR configured RISC-V server.
echo It compiles up to 10 binaries and can consume up to 2 GiB workspace.
choice /C YN /N /M "Approve SSH deployment and start Test 88? [Y/N] "
if errorlevel 2 goto cancelled
"%PY%" tools\rvvlab.py run prequal-8h --wait
if errorlevel 1 goto failed
echo.
echo Run concluded or watcher returned. Check the remote status and sync.
pause
exit /b 0
:missing_python
echo ERROR: create .venv using the regular Lab launcher first.
goto failed
:cancelled
echo Not started.
exit /b 1
:failed
echo.
echo ERROR: Test 88 was not completed. Inspect the message above.
pause
exit /b 1
