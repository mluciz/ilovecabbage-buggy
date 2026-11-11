@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Python 3.11+ required.
 pause
 exit /b 1
)
REM Demo mode uses no Bluetooth and does not need BLE packages.
py app.py --demo
if errorlevel 1 pause
