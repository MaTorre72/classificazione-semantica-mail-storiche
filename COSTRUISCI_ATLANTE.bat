@echo off
setlocal
cd /d "%~dp0"
set "ATLAS=.venv\Scripts\email-atlas.exe"
set /p "WORKSPACE=Cartella workspace [workspace_studio_email]: "
if "%WORKSPACE%"=="" set "WORKSPACE=workspace_studio_email"
if not exist "%WORKSPACE%\classification_workspace.csv" (
  echo ERRORE: classification_workspace.csv non trovato.
  exit /b 1
)
"%ATLAS%" build-atlas --workspace "%WORKSPACE%"
if errorlevel 1 exit /b 1
if exist "%WORKSPACE%\atlas_final.html" start "" "%WORKSPACE%\atlas_final.html"
exit /b 0
