@echo off
REM PyFlipper launcher for Windows - sets up a venv on first run, then starts.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [PyFlipper] First run: creating virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" -m pyflipper %*
