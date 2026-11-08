@echo off
setlocal
set "FLDROPPER_BUILD_CHECK="
if /i "%~1"=="--check" set "FLDROPPER_BUILD_CHECK=-CheckOnly"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-github-build.ps1" %FLDROPPER_BUILD_CHECK%
set "FLDROPPER_BUILD_EXIT=%errorlevel%"
if /i "%~1"=="--check" exit /b %FLDROPPER_BUILD_EXIT%
if /i not "%~1"=="--no-pause" pause
exit /b %FLDROPPER_BUILD_EXIT%
