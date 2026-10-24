#!/bin/bash
# Shared by the macOS launchers; compatible with Apple's Bash 3.2.
find_python() {
    local candidate
    for candidate in python3 python3.12 python3.13 python3.14 python3.15 \
        /opt/homebrew/opt/python@*/bin/python3.* /usr/local/opt/python@*/bin/python3.* \
        /Library/Frameworks/Python.framework/Versions/*/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
            "$candidate" -c 'import sys, venv, ensurepip; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}
find_brew() {
    local candidate
    for candidate in brew /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}
pause_if_needed() {
    if [[ -t 0 && "${1:-}" != "--no-pause" && "${1:-}" != "--check-only" ]]; then
        read -r -p "Press Return to close... " reply || true
    fi
}
