#!/bin/bash
# macOS: run with bash setup.command, or mark executable and double-click.
set -u
cd "$(dirname "$0")" || exit 1

pause_if_needed() {
    if [[ -t 0 && "${1:-}" != "--no-pause" ]]; then
        read -r -p "Press Return to close... " reply
    fi
}
fail() {
    printf '%s\n' "$1"
    pause_if_needed "${2:-}"
    exit 1
}

printf '%s\n' "Setting up FL Dropper..."
if [[ ! -x .venv/bin/python ]]; then
    if [[ -e .venv ]]; then
        fail "The .venv folder has no usable macOS Python. Rename it and rerun setup.command." "${1:-}"
    fi
    python_command=""
    for candidate in python3 python3.14 python3.13 python3.12; do
        if command -v "$candidate" >/dev/null 2>&1 &&
            "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
            python_command="$candidate"
            break
        fi
    done
    if [[ -z "$python_command" ]]; then
        fail "Python 3.12 or newer is required. Install it from https://www.python.org/downloads/ and rerun setup.command." "${1:-}"
    fi
    "$python_command" -m venv .venv || fail "Could not create .venv. Check Python and folder permissions." "${1:-}"
fi

.venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1 ||
    fail "The local environment needs Python 3.12 or newer. Rename .venv and rerun setup.command." "${1:-}"
.venv/bin/python -m pip install . ||
    fail "Installation failed. Check the error above and your internet connection, then rerun setup.command." "${1:-}"
chmod +x setup.command run.command || fail "Could not mark the launch scripts executable." "${1:-}"
printf '\n%s\n' "Setup complete. Double-click run.command to open FL Dropper."
pause_if_needed "${1:-}"
