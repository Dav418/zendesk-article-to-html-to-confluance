@echo off
setlocal
cd /d "%~dp0"

echo %~dp0 | findstr /I /C:"AppData\Local\Temp" >nul
if %errorlevel%==0 (
  echo This was started from inside the ZIP, before it was unzipped.
  echo Close this window.
  echo Right-click the downloaded ZIP, choose Extract All, then Extract.
  echo Open the new folder until you can see start.bat, then double-click that start.bat.
  pause
  exit /b 1
)

if not exist "%~dp0migrate.py" (
  echo Unzip the download first, then run start.bat from inside the unzipped folder.
  echo Do not run it from the ZIP window.
  pause
  exit /b 1
)

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo Python 3.11 or newer is required.
  echo Install it from https://www.python.org/downloads/windows/
  echo During setup, tick "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the Python environment.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto pipfail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

if not exist ".env" goto needenv
findstr /R "[^ ]" ".env" >nul
if errorlevel 1 goto needenv
goto runmigrate

:needenv
if exist ".env.example" copy /Y ".env.example" ".env" >nul
echo.
echo A file named .env must be filled in before the migration can run.
echo It is in this same folder, next to start.bat:
echo   %~dp0.env
echo.
echo If you cannot see .env in File Explorer:
echo   1. Open the unzipped folder, the one that contains start.bat.
echo   2. Click the View menu, then Show.
echo   3. Tick File name extensions.
echo   4. Tick Hidden items.
echo .env is not inside another folder. Do not edit the .venv folder.
echo Notepad will open .env. Replace every example value, including PASTE_ZENDESK_TOKEN_HERE.
echo Then use File, Save, close Notepad, and run start.bat again.
notepad "%~dp0.env"
pause
exit /b 1

:runmigrate

".venv\Scripts\python.exe" migrate.py
set "EXITCODE=%errorlevel%"
echo.
pause
exit /b %EXITCODE%

:pipfail
echo Could not install the Python packages. Check your internet connection and run this again.
pause
exit /b 1
