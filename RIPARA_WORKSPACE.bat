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
echo La riparazione crea un backup e non cancella email o risultati.
set /p "CONFIRM=Procedere? Scrivi RIPARA: "
if /i not "%CONFIRM%"=="RIPARA" exit /b 1
"%ATLAS%" repair-workspace --workspace "%WORKSPACE%"
if errorlevel 1 (
  echo.
  echo Riparazione non eseguita. Usa un workspace nuovo o ripristina un backup.
  exit /b 1
)
echo.
echo Riparazione completata. Esegui ora CONTROLLO_WORKSPACE.bat.
exit /b 0
