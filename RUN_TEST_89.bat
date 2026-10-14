@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
echo.
echo ===== RVV-VLA Lab - Test 89 - corrected 1h native pilot =====
echo.
if not exist "%PY%" goto missing_python
"%PY%" tools\test_prequal_89.py
if errorlevel 1 goto failed
"%PY%" tools\test_disk_safety_200m.py
if errorlevel 1 goto failed
echo.
echo Approved schedule: SIX native C++ backends, 767 JSON designs, 60 minutes total.
echo The first measurements are guarded by mandatory native split smoke tests.
echo Your existing SSH .env is read by Lab; no credentials are written here.
choice /C YN /N /M "Approve SSH deployment and start Test 89? [Y/N] "
if errorlevel 2 goto cancelled
"%PY%" tools\rvvlab.py run prequal-fixed-60m --wait
if errorlevel 1 goto failed
echo.
echo Monitor finished. Check status and results before interpreting trends.
pause
exit /b 0
:missing_python
echo ERROR: .venv\Scripts\python.exe not found.
goto failed
:cancelled
echo Cancelled without SSH run.
exit /b 1
:failed
echo.
echo ERROR: Test 89 not completed. See preceding diagnostic.
pause
exit /b 1
