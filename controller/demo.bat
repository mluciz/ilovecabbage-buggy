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
%PYTHON% -c "import sys,tkinter; assert sys.version_info >= (3,11)" >nul 2>&1
if errorlevel 1 goto :missing
echo OFFLINE DEMO: no actual BLE or motors will be commanded.
%PYTHON% app.py --demo
if errorlevel 1 pause
exit /b 0
:missing
echo Python 3.11+ with Tkinter required. Install from python.org.
pause
exit /b 1
