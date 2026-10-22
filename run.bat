@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo FL Dropper is not set up. Run setup.bat first.
    goto failed
)
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 12); import PySide6" >nul 2>&1
if errorlevel 1 (
    echo The local Python environment needs repair. Run setup.bat first.
    goto failed
)
if not exist ".venv\Scripts\pythonw.exe" (
    echo The local windowed Python interpreter is missing. Run setup.bat first.
    goto failed
)
start "" ".venv\Scripts\pythonw.exe" -m fldropper
if errorlevel 1 goto failed
popd
exit /b 0

:failed
echo FL Dropper could not start or exited with an error. See the messages above.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
