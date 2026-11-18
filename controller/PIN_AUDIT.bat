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
echo Source PIN AUDIT: code mapping only, NO live device test.
%PYTHON% -c "from wheel_doctor import audit_sources; ok,lines=audit_sources(); print(chr(10).join(lines)); raise SystemExit(0 if ok else 1)"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo PIN SOURCE CHECK FAILED. Do not flash motors until fixed.
pause
exit /b %RESULT%
:missing
echo Python 3.11+ not found.
pause
exit /b 1
