@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Python launcher not found. Install Python 3.11+.
 pause
 exit /b 1
)
py -m pip install -r requirements.txt pytest
if errorlevel 1 (
  pause
  exit /b 1
 )
py -m pytest -q
pause
