#!/bin/bash
# macOS: run with bash setup.command, or mark executable and double-click.
set -u
cd "$(dirname "$0")" || exit 1
source scripts/macos-common.sh || exit 1
fail() {
    printf '%s\n' "$1"
    pause_if_needed "${2:-}"
    exit 1
}
if [[ "$(uname -s)" != Darwin ]]; then
    fail "setup.command is for macOS only. On Windows use setup.bat." "${1:-}"
fi
check_venv() {
    [[ -x .venv/bin/python ]] &&
        .venv/bin/python -c 'import sys, pathlib, pip; raise SystemExit(sys.version_info < (3, 12) or sys.prefix == sys.base_prefix or pathlib.Path(sys.prefix).resolve() != pathlib.Path(".venv").resolve())' >/dev/null 2>&1
}
printf '%s\n' "Setting up FL Dropper..."
if ! check_venv; then
    bash get-python.command --no-pause || fail "Python setup did not finish. Follow the instructions above and retry." "${1:-}"
    python_command="$(find_python)" || fail "Could not locate compatible Python after setup." "${1:-}"
    # This target is fixed beneath the physical app folder. rm does not follow
    # symlinks inside it; normal macOS venvs contain interpreter symlinks.
    project_root="$(pwd -P)" || exit 1
    venv_path="$project_root/.venv"
    [[ "$venv_path" == "$project_root/.venv" && "$(dirname "$venv_path")" == "$project_root" ]] || exit 1
    [[ ! -L "$venv_path" ]] || fail "The .venv is a symlink. Remove the link manually and rerun setup." "${1:-}"
    if [[ -e "$venv_path" ]]; then
        printf '%s\n' "Removing unusable environment: $venv_path"
        rm -rf -- "$venv_path" || fail "Could not clean .venv. Close FL Dropper and check permissions." "${1:-}"
    fi
    "$python_command" -m venv .venv || fail "Could not create .venv. Check Python and folder permissions." "${1:-}"
    check_venv || fail "The rebuilt environment is unusable. Check Python and rerun setup." "${1:-}"
fi
.venv/bin/python -m pip install . ||
    fail "Installation failed. Check the error above and your internet connection, then rerun setup.command." "${1:-}"
chmod +x setup.command get-python.command run.command "FL Dropper.app/Contents/MacOS/FLDropper" ||
    fail "Could not mark launchers executable. Keep FL Dropper.app in this folder and rerun setup." "${1:-}"
printf '\n%s\n' "Setup complete. Double-click FL Dropper.app to open FL Dropper without Terminal."
pause_if_needed "${1:-}"
