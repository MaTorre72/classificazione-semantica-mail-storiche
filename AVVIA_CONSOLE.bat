@echo off
setlocal
cd /d "%~dp0"

set "APP=.venv\Scripts\email-cluster.exe"
set "DB=data\email_cluster.sqlite"
set "URL=http://127.0.0.1:8765"

if not exist "%APP%" (
    echo ERRORE: ambiente virtuale non pronto.
    echo Esegui: .\.venv\Scripts\python.exe -m pip install -e .[ui]
    pause
    exit /b 1
)

if not exist "%DB%" (
    echo ERRORE: database non trovato: %DB%
    pause
    exit /b 1
)

echo Avvio Archivio storico...
echo La console sara disponibile su %URL%
start "" "%URL%"
"%APP%" ui --project archivio_storico --db "%DB%" --no-open-browser

if errorlevel 1 (
    echo.
    echo La console si e chiusa con un errore.
    pause
)
