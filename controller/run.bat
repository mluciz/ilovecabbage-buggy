@echo off
cd /d "%~dp0\.."
py -m controller.app
if errorlevel 1 (
  echo.
  echo Installation: py -m pip install -r controller\requirements.txt
  pause
)
