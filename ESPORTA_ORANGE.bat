@echo off
setlocal
cd /d "%~dp0"
set "ATLAS=.venv\Scripts\email-atlas.exe"
if not exist "%ATLAS%" (
  echo ERRORE: ambiente non pronto.
  exit /b 1
)
set /p "WORKSPACE=Cartella workspace [workspace_studio_email]: "
if "%WORKSPACE%"=="" set "WORKSPACE=workspace_studio_email"
if not exist "%WORKSPACE%\workspace.json" (
  echo ERRORE: workspace.json non trovato.
  exit /b 1
)
"%ATLAS%" export-orange --workspace "%WORKSPACE%"
if errorlevel 1 exit /b 1
echo Pacchetto Orange creato in: %WORKSPACE%\orange
if not defined EMAIL_ATLAS_NO_OPEN start "" "%WORKSPACE%\orange"
exit /b 0
