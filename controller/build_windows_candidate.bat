@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.11+ first.
 pause
 exit /b 1
)
echo.
echo Building a LOCAL TEST CANDIDATE. NOT CERTIFIED FOR DRIVING.
echo.
py -m pip install -r requirements.txt "pyinstaller>=6,<8"
if errorlevel 1 goto :failure
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "Cabbage-Studio-v18-CANDIDATE" --paths "." --add-data "arduino;arduino" --add-data "app.py;." --add-data "ble_bridge.py;." --add-data "WHEEL_DOCTOR_FIELD_GUIDE.md;." --hidden-import "bleak.backends.winrt" app.py
if errorlevel 1 goto :failure
echo.
echo Candidate EXE: %CD%\dist\Cabbage-Studio-v18-CANDIDATE.exe
echo This EXE does NOT flash Arduino firmware, verify motor wiring or measure wheel speed.
pause
exit /b 0
:failure
echo Build failed; use run.bat with a supported Python installation.
pause
exit /b 1
