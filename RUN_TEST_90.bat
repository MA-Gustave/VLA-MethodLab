@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
echo.
echo ===== RVV-VLA Lab - Test 90: 2-hour independent holdout =====
echo.
if not exist "%PY%" goto missing_python
"%PY%" tools\test_holdout_90.py
if errorlevel 1 goto failed
echo.
echo Approval: 5 native configurations, 2-hour maximum including compilation.
echo JSON is newly generated and three full primary repeat rounds are prioritized.
echo Existing .env is read without copying credentials; remote 200 MiB safety stop remains.
choice /C YN /N /M "Approve SSH deployment and start Test 90? [Y/N] "
if errorlevel 2 goto cancelled
"%PY%" tools\rvvlab.py run holdout-2h --wait
if errorlevel 1 goto failed
echo.
echo Run ended. Sync results from Lab Studio if not already present.
pause
exit /b 0
:missing_python
echo ERROR: local .venv missing.
goto failed
:cancelled
echo Cancelled without remote work.
exit /b 1
:failed
echo ERROR: Test 90 not completed. Inspect the preceding diagnostic.
pause
exit /b 1
