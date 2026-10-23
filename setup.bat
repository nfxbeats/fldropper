@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "FLDROPPER_EXIT=1"

echo Setting up FL Dropper...
if exist ".venv\Scripts\python.exe" goto install
if exist ".venv" (
    echo The .venv folder exists but has no Windows Python interpreter.
    echo Rename it and run setup.bat again to create a Windows environment.
    goto finish 
)

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if not errorlevel 1 goto create_py
python -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if not errorlevel 1 goto create_python
echo Python 3.12 or newer is required. Install it from https://www.python.org/downloads/
echo Then run setup.bat again.
goto finish

:create_py
py -3 -m venv ".venv"
if errorlevel 1 goto venv_failed
goto install

:create_python
python -m venv ".venv"
if errorlevel 1 goto venv_failed
goto install

:venv_failed
echo Could not create .venv. Check the Python installation and folder permissions.
goto finish

:install
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if errorlevel 1 (
    echo The existing .venv is unavailable or uses Python older than 3.12.
    echo Rename .venv and run setup.bat again.
    goto finish
)
".venv\Scripts\python.exe" -m pip install .
if errorlevel 1 (
    echo Installation failed. Check the error above and your internet connection, then rerun setup.bat.
    goto finish
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\create-shortcut.ps1"
if errorlevel 1 (
    echo Desktop shortcut creation failed. You can still open the app using run.bat.
)
echo.
echo Setup complete. Double-click run.bat to open FL Dropper.
set "FLDROPPER_EXIT=0"

:finish
popd
if /i not "%~1"=="--no-pause" pause
exit /b %FLDROPPER_EXIT%
