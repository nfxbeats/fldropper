@echo off
setlocal
set "FLDROPPER_EXIT=1"

echo Checking for Python 3.12 or newer...
call :detect_python
if not errorlevel 1 goto already_installed
if /i "%~1"=="--check-only" goto missing

echo.
echo No compatible Python installation was found.
echo This can attempt to install Python 3.12 for your Windows user using WinGet.
echo Internet access is required. WinGet may ask you to accept license terms.
echo After Python is ready, FL Dropper setup can continue.
echo.
choice /c YN /n /m "Attempt to install Python now? [Y/N]: "
if errorlevel 2 goto declined
if errorlevel 1 goto install_python
goto declined

:install_python
where winget.exe >nul 2>&1
if errorlevel 1 goto no_winget
echo.
echo Installing Python 3.12 for the current user...
winget.exe install --id Python.Python.3.12 --exact --source winget --scope user --interactive
if errorlevel 1 goto install_failed
call :detect_python
if not errorlevel 1 goto installed
echo.
echo WinGet finished, but this window cannot find compatible Python yet.
echo Close this window and run get-python.bat again to refresh the environment.
echo If it is still missing, install Python from https://www.python.org/downloads/
goto finish

:already_installed
echo Compatible Python is already installed. Nothing was installed or changed.
if /i not "%~2"=="--from-setup" echo Next: run setup.bat to set up FL Dropper.
set "FLDROPPER_EXIT=0"
goto finish

:installed
echo.
echo Python is ready.
if /i not "%~2"=="--from-setup" echo Close this window, then run setup.bat.
set "FLDROPPER_EXIT=0"
goto finish

:missing
echo No compatible Python installation was found.
goto finish

:declined
echo.
echo Installation cancelled. Nothing was installed.
goto finish

:no_winget
echo.
echo WinGet is unavailable, so automatic installation could not be attempted.
echo Install Python 3.12 or newer from https://www.python.org/downloads/
echo Enable Add Python to PATH if the installer offers it, then run setup.bat.
goto finish

:install_failed
echo.
echo Python installation did not complete. See the WinGet message above.
echo You can retry, or install Python from https://www.python.org/downloads/
goto finish

:finish
if /i "%~1"=="--no-pause" exit /b %FLDROPPER_EXIT%
if /i "%~1"=="--check-only" exit /b %FLDROPPER_EXIT%
pause
exit /b %FLDROPPER_EXIT%

:detect_python
py -3 -c "import sys; print(sys.executable); print(sys.version.split()[0]); raise SystemExit(sys.version_info < (3, 12))" 2>nul
if not errorlevel 1 exit /b 0
python -c "import sys; print(sys.executable); print(sys.version.split()[0]); raise SystemExit(sys.version_info < (3, 12))" 2>nul
if not errorlevel 1 exit /b 0
rem Also find a new per-user install before this process's PATH refreshes.
if not defined LOCALAPPDATA exit /b 1
if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" exit /b 1
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys; print(sys.executable); print(sys.version.split()[0]); raise SystemExit(sys.version_info < (3, 12))" 2>nul
exit /b %errorlevel%
