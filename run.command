#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1

pause_if_needed() {
    if [[ -t 0 && "${1:-}" != "--no-pause" ]]; then
        read -r -p "Press Return to close... " reply
    fi
}
if [[ ! -x .venv/bin/python ]]; then
    printf '%s\n' "FL Dropper is not set up. Run setup.command first."
    pause_if_needed "${1:-}"
    exit 1
fi
if ! .venv/bin/python -c 'import sys; assert sys.version_info >= (3, 12); import PySide6' >/dev/null 2>&1; then
    printf '%s\n' "The local Python environment needs repair. Run setup.command first."
    pause_if_needed "${1:-}"
    exit 1
fi
if .venv/bin/python -m fldropper; then
    exit 0
else
    app_status=$?
    printf '%s\n' "FL Dropper exited with an error. See the messages above."
    pause_if_needed "${1:-}"
    exit "$app_status"
fi
