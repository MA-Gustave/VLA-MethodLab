@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM RVV-VLA Lab - one-click integrated Studio launcher - v5.
REM All files are located relative to the folder containing this BAT.
REM No PowerShell, no gh login, no automatic SSH connection.
REM No parenthesized CMD blocks: avoids accidental syntax errors.

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PYTHONW=%VENV%\Scripts\pythonw.exe"
set "CHECK=%ROOT%studio\check_runtime.py"
set "APP=%ROOT%studio\RVV_Lab_Studio.pyw"
set "REQ=%ROOT%studio\requirements.txt"

echo.
echo ===== RVV-VLA Lab - Integrated Studio =====
echo.
if not exist "%APP%" goto missing_app
if not exist "%CHECK%" goto missing_check
if not exist "%REQ%" goto missing_requirements
if not exist "%PYTHON%" goto create_venv
goto check_dependencies

:create_venv
echo Creating a local Python virtual environment...
where py.exe >nul 2>nul
if not errorlevel 1 goto create_with_py
where python.exe >nul 2>nul
if errorlevel 1 goto missing_python
python.exe -m venv "%VENV%"
if errorlevel 1 goto venv_failed
goto check_dependencies

:create_with_py
py -3 -m venv "%VENV%"
if errorlevel 1 goto venv_failed
goto check_dependencies

:check_dependencies
if not exist "%PYTHON%" goto venv_failed
"%PYTHON%" "%CHECK%" tkinter
if errorlevel 1 goto tkinter_failed
"%PYTHON%" "%CHECK%" paramiko
if errorlevel 1 goto install_paramiko
goto check_studio

:install_paramiko
echo.
echo Paramiko is missing from this local environment.
set "ANSWER="
set /p "ANSWER=Install Paramiko in the local .venv? [Y/n]: "
if /I "%ANSWER%"=="n" goto declined
if /I "%ANSWER%"=="no" goto declined
if /I "%ANSWER%"=="non" goto declined
"%PYTHON%" -m pip install --disable-pip-version-check -r "%REQ%"
if errorlevel 1 goto install_failed
"%PYTHON%" "%CHECK%" paramiko
if errorlevel 1 goto install_failed

:check_studio
"%PYTHON%" "%CHECK%" studio
if errorlevel 1 goto studio_failed
if not exist "%PYTHONW%" goto pythonw_missing

echo Launching the integrated GUI...
start "" /D "%ROOT%studio" "%PYTHONW%" "%APP%"
if errorlevel 1 goto gui_failed
echo GUI launch requested. SSH remains disconnected until you connect.
exit /b 0

:missing_app
echo ERROR: Studio GUI is missing: "%APP%"
goto error
:missing_check
echo ERROR: runtime checker is missing: "%CHECK%"
echo Install the v4 launcher prerequisite files first.
goto error
:missing_requirements
echo ERROR: Studio requirements are missing: "%REQ%"
goto error
:missing_python
echo ERROR: Python 3.10 or newer is not available on PATH.
goto error
:venv_failed
echo ERROR: could not create or use the local Python .venv.
goto error
:tkinter_failed
echo ERROR: Python needs Tkinter support to open Studio.
goto error
:install_failed
echo ERROR: Paramiko installation or import failed.
goto error
:studio_failed
echo ERROR: the Studio import check failed.
goto error
:pythonw_missing
echo ERROR: pythonw.exe is missing from the local .venv.
goto error
:gui_failed
echo ERROR: Windows could not start the GUI process.
goto error
:declined
echo Paramiko installation cancelled. Nothing was started.
exit /b 1
:error
echo.
echo The Studio was NOT launched. Review the error above.
pause
exit /b 1
