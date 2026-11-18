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
%PYTHON% -m pip install -r requirements.txt pytest
if errorlevel 1 (
  echo Could not install test dependencies.
  pause
  exit /b 1
)
%PYTHON% -m pytest -q
echo.
echo Test output above reflects SOFTWARE and firmware-mock checks only.
echo Physical motor direction, battery power and braking still require real bench checks.
pause
exit /b %ERRORLEVEL%
:missing
echo Python 3.11+ not found.
pause
exit /b 1
