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

".venv\Scripts\python.exe" migrate.py
set "EXITCODE=%errorlevel%"
echo.
pause
exit /b %EXITCODE%

:pipfail
echo Could not install the Python packages. Check your internet connection and run this again.
pause
exit /b 1
