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
set "REBUILD="
if exist "%WORKSPACE%\email_atlas.sqlite" (
  echo.
  echo Se hai aggiunto nuove cartelle o messaggi a uno studio gia elaborato,
  echo occorre ricostruire conversazioni e derivati. Verra creato un backup SQLite.
  set /p "RICOSTRUISCI=Ricostruire conversazioni con backup? [s/N]: "
  if /i "%RICOSTRUISCI%"=="s" set "REBUILD=--rebuild-stage build_conversations"
)

echo.
echo Avvio studio locale. Non chiudere questa finestra.
"%ATLAS%" study --input "%INPUT%" --workspace "%WORKSPACE%" %ATTACH% %REBUILD%
if errorlevel 1 (
  echo ERRORE: consultare il messaggio sopra.
  exit /b 1
)
echo.
echo Studio completato: %WORKSPACE%
if exist "%WORKSPACE%\study_report.html" if not defined EMAIL_ATLAS_NO_OPEN start "" "%WORKSPACE%\study_report.html"
exit /b 0
