@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" goto no_python
"%PY%" "%ROOT%tools\pull_run_diagnostics.py" %*
if errorlevel 1 goto failed
echo.
echo Results saved under results\local. Please upload the diagnostics ZIP here.
pause
exit /b 0
:no_python
echo ERROR: no local Python environment found in .venv\Scripts\python.exe
pause
exit /b 2
:failed
echo ERROR: diagnostic retrieval failed. No remote data was deleted.
pause
exit /b 1
