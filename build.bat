@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "FLDROPPER_BUILD_EXIT=1"

where /q git
if errorlevel 1 (
    echo Install Git for Windows, then rerun build.bat.
    goto finish
)
where /q gh
if errorlevel 1 (
    echo Install GitHub CLI from https://cli.github.com and run gh auth login.
    goto finish
)
gh auth status >nul 2>&1
if errorlevel 1 (
    echo Run gh auth login, then rerun build.bat.
    goto finish
)
set "FLDROPPER_BUILD_BRANCH="
for /f "delims=" %%B in ('git symbolic-ref --quiet --short HEAD') do set "FLDROPPER_BUILD_BRANCH=%%B"
if not defined FLDROPPER_BUILD_BRANCH (
    echo Check out the branch you want to build, then rerun build.bat.
    goto finish
)
set "FLDROPPER_BUILD_DIRTY="
for /f "delims=" %%S in ('git status --porcelain') do set "FLDROPPER_BUILD_DIRTY=1"
if defined FLDROPPER_BUILD_DIRTY (
    echo Commit and push your changes first. GitHub Actions builds the pushed code.
    goto finish
)
set "FLDROPPER_BUILD_REPO="
for /f "delims=" %%R in ('git remote get-url origin') do set "FLDROPPER_BUILD_REPO=%%R"
if not defined FLDROPPER_BUILD_REPO (
    echo Configure the origin remote for your GitHub repository first.
    goto finish
)
echo Checking the pushed version on origin/%FLDROPPER_BUILD_BRANCH%...
git fetch --quiet origin "%FLDROPPER_BUILD_BRANCH%"
if errorlevel 1 goto finish
for /f %%H in ('git rev-parse HEAD') do set "FLDROPPER_BUILD_LOCAL=%%H"
for /f %%H in ('git rev-parse FETCH_HEAD') do set "FLDROPPER_BUILD_REMOTE=%%H"
if not "%FLDROPPER_BUILD_LOCAL%"=="%FLDROPPER_BUILD_REMOTE%" (
    echo Local and GitHub commits differ. Synchronize your branch and push before building.
    goto finish
)
if /i "%~1"=="--check" (
    echo Checks passed. No workflow was started.
    set "FLDROPPER_BUILD_EXIT=0"
    goto finish
)

echo Starting GitHub Actions: Build desktop apps on %FLDROPPER_BUILD_BRANCH%...
gh workflow run pyinstaller-build.yaml --repo "%FLDROPPER_BUILD_REPO%" --ref "%FLDROPPER_BUILD_BRANCH%"
if errorlevel 1 goto finish

echo.
echo Workflow requested. Windows and macOS ZIPs will be available in its artifacts.
echo The build version comes from fldropper/__init__.py in the pushed commit.
gh run list --repo "%FLDROPPER_BUILD_REPO%" --workflow pyinstaller-build.yaml --branch "%FLDROPPER_BUILD_BRANCH%" --limit 3
set "FLDROPPER_BUILD_EXIT=0"

:finish
if not "%FLDROPPER_BUILD_EXIT%"=="0" echo Workflow was not started. Check the error above.
popd
if /i "%~1"=="--check" exit /b %FLDROPPER_BUILD_EXIT%
if /i not "%~1"=="--no-pause" pause
exit /b %FLDROPPER_BUILD_EXIT%
