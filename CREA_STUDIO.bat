@echo off
setlocal
cd /d "%~dp0"
set "ATLAS=.venv\Scripts\email-atlas.exe"
if not exist "%ATLAS%" (
  echo ERRORE: ambiente non pronto.
  exit /b 1
)

echo Indica la cartella COPIA dello snapshot Thunderbird/MBOX.
set /p "INPUT=Snapshot MBOX: "
if not exist "%INPUT%" (
  echo ERRORE: cartella non trovata.
  exit /b 1
)
set /p "WORKSPACE=Workspace [workspace_studio_email]: "
if "%WORKSPACE%"=="" set "WORKSPACE=workspace_studio_email"
set /p "ALLEGATI=Estrarre testo allegati supportati? [S/n]: "
set "ATTACH=--with-attachments-text"
if /i "%ALLEGATI%"=="n" set "ATTACH=--no-attachments-text"

echo.
echo Avvio studio locale. Non chiudere questa finestra.
"%ATLAS%" study --input "%INPUT%" --workspace "%WORKSPACE%" %ATTACH%
if errorlevel 1 (
  echo ERRORE: consultare il messaggio sopra.
  exit /b 1
)
echo.
echo Studio completato: %WORKSPACE%
if exist "%WORKSPACE%\study_report.html" start "" "%WORKSPACE%\study_report.html"
exit /b 0
