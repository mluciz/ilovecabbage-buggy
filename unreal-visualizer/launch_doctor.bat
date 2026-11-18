@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\doctor.py
) else (
    python tools\doctor.py
)
echo.
echo The preflight cannot verify physical wiring or compile Unreal.
pause
