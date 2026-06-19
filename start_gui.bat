@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\email-cluster-gui.exe" (
    echo Ambiente non pronto. Esegui prima:
    echo .\.venv\Scripts\python.exe -m pip install -e .[dev]
    pause
    exit /b 1
)
".venv\Scripts\email-cluster-gui.exe"
