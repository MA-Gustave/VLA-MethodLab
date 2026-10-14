@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
 echo Local Python environment missing. Run LAUNCH_RVV_VLA_LAB.bat first.
 pause
 exit /b 1
)
"%PY%" tools\test_exploration_91.py
if errorlevel 1 goto failed
choice /C YN /N /M "Deploy and start Test91 explore-91-pilot on the RISC-V server? [Y/N] "
if errorlevel 2 exit /b 1
"%PY%" tools\rvvlab.py run explore-91-pilot --wait
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Test91 stopped with an error. Read the diagnostic above.
pause
exit /b 1
