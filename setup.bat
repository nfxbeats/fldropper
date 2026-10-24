@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "FLDROPPER_EXIT=1"
set "FLDROPPER_PYTHON_FLAG="

echo Setting up FL Dropper...
call :check_venv
if not errorlevel 1 goto install

call "%~dp0get-python.bat" --no-pause --from-setup
if errorlevel 1 goto finish
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if not errorlevel 1 (
    set "FLDROPPER_PYTHON=py"
    set "FLDROPPER_PYTHON_FLAG=-3"
    goto rebuild
)
python -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if not errorlevel 1 (
    set "FLDROPPER_PYTHON=python"
    goto rebuild
)
if not defined LOCALAPPDATA goto python_missing
if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto python_missing
set "FLDROPPER_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
"%FLDROPPER_PYTHON%" -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if errorlevel 1 goto python_missing

:rebuild
rem The helper validates this exact project's .venv before removing anything.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\clean-venv.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto finish
"%FLDROPPER_PYTHON%" %FLDROPPER_PYTHON_FLAG% -m venv ".venv"
if errorlevel 1 goto venv_failed
call :check_venv
if errorlevel 1 goto venv_failed

:install
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
goto finish

:python_missing
echo Compatible Python could not be found. Close this window and rerun setup.bat.
goto finish

:venv_failed
echo Could not create a usable .venv. Close FL Dropper and check folder permissions, then rerun setup.bat.
goto finish

:finish
popd
if /i not "%~1"=="--no-pause" pause
exit /b %FLDROPPER_EXIT%

:check_venv
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" -c "import sys, pathlib, pip; expected = pathlib.Path('.venv').resolve(); raise SystemExit(sys.version_info < (3, 12) or sys.prefix == sys.base_prefix or pathlib.Path(sys.prefix).resolve() != expected)" >nul 2>&1
exit /b %errorlevel%
