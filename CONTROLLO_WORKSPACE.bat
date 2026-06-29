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
"%ATLAS%" doctor-workspace --workspace "%WORKSPACE%"
if errorlevel 1 (
  echo.
  echo Workspace non integro. Leggi NEXT_STEP sopra prima di riprovare lo studio.
  exit /b 1
)
echo.
echo Workspace integro.
exit /b 0
