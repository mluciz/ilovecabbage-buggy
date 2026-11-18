@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=py -3"
where py >nul 2>&1
if errorlevel 1 (
  set "PYTHON=python"
  where python >nul 2>&1
  if errorlevel 1 goto :missing
)
%PYTHON% -c "import sys, tkinter; assert sys.version_info >= (3,11), 'Python 3.11+ required'" >nul 2>&1
if errorlevel 1 (
  echo Python 3.11+ with Tkinter required. Install from python.org and enable Add to PATH.
  pause
  exit /b 1
)
%PYTHON% -c "import bleak,serial" >nul 2>&1
if errorlevel 1 (
  echo Installing missing Bluetooth dependencies for this Python interpreter...
  %PYTHON% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Could not install BLE dependencies. Run demo.bat to explore safely offline.
    pause
    exit /b 1
  )
)
echo Starting Buggy Control Center Field Lab. Use F1 for Wheel Doctor.
%PYTHON% app.py
if errorlevel 1 (
  echo App terminated with an error. See messages above.
  pause
)
exit /b 0
:missing
echo Python 3.11+ not found. Install Python from https://www.python.org/downloads/
pause
exit /b 1
