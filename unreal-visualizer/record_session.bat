@echo off
setlocal
cd /d "%~dp0"
if not exist sessions mkdir sessions
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')"') do set STAMP=%%I
if "%STAMP%"=="" set STAMP=manual
echo.
echo CABBAGE SPATIAL LAB - RECORDING
echo Feed sensors/simulation to UDP port 48764, proxy forwards to Unreal port 48765.
echo Stop by pressing Ctrl+C. No motors are controlled by this script.
echo.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\session_tool.py capture --out "sessions\session_%STAMP%.jsonl"
) else (
    python tools\session_tool.py capture --out "sessions\session_%STAMP%.jsonl"
)
pause
