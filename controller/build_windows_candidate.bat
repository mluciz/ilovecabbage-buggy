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
echo Staging Unreal Spatial Lab C++ project beside candidate EXE...
if exist "..\unreal-visualizer\BuggySensorViz.uproject" (
  xcopy /E /I /Y "..\unreal-visualizer" "dist\unreal-visualizer" >nul
  if errorlevel 1 goto :failure
) else (
  echo WARNING: Unreal source not in sibling folder. Use source checkout or Browse from the app.
)
echo.
echo Candidate EXE: %CD%\dist\Cabbage-Studio-v18-CANDIDATE.exe
echo Spatial Lab sidecar: %CD%\dist\unreal-visualizer\BuggySensorViz.uproject
echo This EXE does NOT flash Arduino firmware, verify motor wiring or measure wheel speed.
pause
exit /b 0
:failure
echo Build failed; use run.bat with a supported Python installation.
pause
exit /b 1
