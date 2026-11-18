@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\demo_sender.py --scenario arena
) else (
    python tools\demo_sender.py --scenario arena
)
pause
