#!/usr/bin/env bash
# PyFlipper launcher for Linux/macOS - sets up a venv on first run, then starts.
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[PyFlipper] First run: creating virtual environment..."
    python3 -m venv .venv
    ./.venv/bin/python -m pip install --upgrade pip
    ./.venv/bin/python -m pip install -r requirements.txt
fi

exec ./.venv/bin/python -m pyflipper "$@"
