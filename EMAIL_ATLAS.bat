@echo off
setlocal
cd /d "%~dp0"
set "ATLAS=.venv\Scripts\email-atlas.exe"

if not exist "%ATLAS%" (
  echo ERRORE: ambiente Python non pronto.
  echo Esegui: .\.venv\Scripts\python.exe -m pip install -e .[ui,attachments]
  pause
  exit /b 1
)

:menu
cls
echo =====================================================
echo EMAIL ATLAS - STUDIO ARCHIVIO STORICO
echo =====================================================
echo 1. Crea o aggiorna uno studio da snapshot MBOX
echo 2. Costruisci Atlante finale dal workspace revisionato
echo 3. Genera pacchetto Orange
echo 4. Apri interfaccia grafica minima
echo 5. Apri guida completa
echo 6. Controlla integrita workspace
echo 7. Ripara workspace con backup
echo 0. Esci
echo.
set /p "SCELTA=Scelta: "
if "%SCELTA%"=="1" call CREA_STUDIO.bat
if "%SCELTA%"=="2" call COSTRUISCI_ATLANTE.bat
if "%SCELTA%"=="3" call ESPORTA_ORANGE.bat
if "%SCELTA%"=="4" call AVVIA_CONSOLE.bat
if "%SCELTA%"=="5" start "" "docs\guida_uso_completa.md"
if "%SCELTA%"=="6" call CONTROLLO_WORKSPACE.bat
if "%SCELTA%"=="7" call RIPARA_WORKSPACE.bat
if "%SCELTA%"=="0" exit /b 0
pause
goto menu
