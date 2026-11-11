@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.11+ with the Windows launcher from https://www.python.org/downloads/
 pause
 exit /b 1
)
py -c "import bleak,serial" >nul 2>&1
if errorlevel 1 (
 echo Installing missing BLE dependencies (one-time setup)...
 py -m pip install -r requirements.txt
 if errorlevel 1 (
  echo Could not install dependencies. Run demo.bat for offline mode.
  pause
  exit /b 1
 )
)
py app.py
if errorlevel 1 pause
