@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
 echo Local Python environment missing. Run LAUNCH_RVV_VLA_LAB.bat first.
 pause
 exit /b 1
)
"%PY%" tools\test_exploration_93.py
if errorlevel 1 goto failed
choice /C YN /N /M "Deploy and start Test93 Stage1/overhead <=3h on the RISC-V server? [Y/N] "
if errorlevel 2 exit /b 1
"%PY%" tools\rvvlab.py run diagnose-93-3h --wait
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Test93 stopped with an error. Read the diagnostic above.
pause
exit /b 1
