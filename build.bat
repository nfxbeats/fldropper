@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "FLDROPPER_BUILD_EXIT=1"

if exist ".venv\Scripts\python.exe" goto check_venv
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv ".venv"
    if errorlevel 1 goto finish
    goto check_venv
)
python -c "import sys; raise SystemExit(sys.version_info < (3, 12))" >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 or newer is required. Run setup.bat first, then rerun build.bat.
    goto finish
)
python -m venv ".venv"
if errorlevel 1 goto finish

:check_venv
".venv\Scripts\python.exe" -c "import sys, pathlib, pip; expected = pathlib.Path('.venv').resolve(); raise SystemExit(sys.version_info < (3, 12) or sys.prefix == sys.base_prefix or pathlib.Path(sys.prefix).resolve() != expected)" >nul 2>&1
if errorlevel 1 (
    echo The project .venv is not usable. Run setup.bat to repair it, then rerun build.bat.
    goto finish
)

echo Building the version defined in fldropper\__init__.py:
".venv\Scripts\python.exe" -c "import runpy; print(runpy.run_path('fldropper/__init__.py')['__version__'])"
if errorlevel 1 goto finish

echo Installing application and build dependencies...
".venv\Scripts\python.exe" -m pip install . "PyInstaller==6.22.3" "Pillow>=10,<13"
if errorlevel 1 goto finish

echo Building, checking the bundled app, and creating the versioned ZIP...
".venv\Scripts\python.exe" ".github\packaging\build.py"
if errorlevel 1 goto finish

echo.
echo Build complete. The versioned ZIP is in .github\packaging\dist.
set "FLDROPPER_BUILD_EXIT=0"

:finish
if not "%FLDROPPER_BUILD_EXIT%"=="0" echo Build failed. Check the error above.
popd
if /i not "%~1"=="--no-pause" pause
exit /b %FLDROPPER_BUILD_EXIT%
