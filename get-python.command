#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1
source scripts/macos-common.sh || exit 1
finish() { pause_if_needed "${1:-}"; exit "$2"; }
if [[ "$(uname -s)" != Darwin ]]; then
    printf '%s\n' "get-python.command is for macOS only. On Windows use get-python.bat."
    finish "${1:-}" 1
fi
printf '%s\n' "Checking for Python 3.12 or newer..."
if python_command="$(find_python)"; then
    "$python_command" --version
    printf '%s\n' "Compatible Python is already installed. Nothing was changed."
    finish "${1:-}" 0
fi
printf '%s\n' "No compatible Python installation was found."
[[ "${1:-}" == --check-only ]] && exit 1
if brew_command="$(find_brew)"; then
    printf '%s\n' "Homebrew is available. Install Python 3.12 using Homebrew?"
    read -r -p "Attempt installation? [y/N]: " reply || reply=""
    case "$reply" in y|Y|yes|YES) ;; *) printf '%s\n' "Installation cancelled. Nothing was installed."; finish "${1:-}" 1 ;; esac
    if ! "$brew_command" install python@3.12; then
        printf '%s\n' "Homebrew installation failed. See the error above, or use https://www.python.org/downloads/macos/"
        finish "${1:-}" 1
    fi
    if python_command="$(find_python)"; then
        "$python_command" --version
        printf '%s\n' "Python is ready."
        finish "${1:-}" 0
    fi
    printf '%s\n' "Python is not available to this window yet. Close it and rerun setup.command."
    finish "${1:-}" 1
fi
printf '%s\n' "Homebrew is unavailable. You can install Python using the official macOS installer." \
    "The installer may ask for an administrator password."
read -r -p "Open the official Python download page? [y/N]: " reply || reply=""
case "$reply" in
    y|Y|yes|YES)
        open 'https://www.python.org/downloads/macos/' || printf '%s\n' "Open https://www.python.org/downloads/macos/ in your browser."
        printf '%s\n' "Download and finish the Python installer, then rerun setup.command."
        ;;
    *) printf '%s\n' "Installation cancelled. Nothing was installed." ;;
esac
finish "${1:-}" 1
