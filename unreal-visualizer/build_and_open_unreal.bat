@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo ========================================
echo  CABBAGE SPATIAL LAB - UNREAL 5.4 BUILD
echo ========================================
echo.
if not exist "BuggySensorViz.uproject" (
    echo ERROR: Unreal project file is missing.
    pause
    exit /b 2
)
if "%UE_ROOT%"=="" set "UE_ROOT=%ProgramFiles%\Epic Games\UE_5.4"
set "UE_BUILD=%UE_ROOT%\Engine\Build\BatchFiles\Build.bat"
set "UE_EDITOR=%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor.exe"
if not exist "%UE_BUILD%" (
    echo ERROR: Unreal 5.4 build tools not found at:
    echo   %UE_BUILD%
    echo Install UE 5.4 or set UE_ROOT to its installation directory.
    echo To check your environment first run launch_doctor.bat.
    pause
    exit /b 3
)
if not exist "%UE_EDITOR%" (
    echo ERROR: UnrealEditor.exe not found at %UE_EDITOR%
    pause
    exit /b 3
)
echo Building native BuggySensorVizEditor C++ target...
echo Motor app and Arduino firmware are NOT modified.
call "%UE_BUILD%" BuggySensorVizEditor Win64 Development -Project="%CD%\BuggySensorViz.uproject" -WaitMutex -NoHotReload
if errorlevel 1 (
    echo.
    echo Unreal C++ compilation FAILED.
    echo Read the compile messages above. Do not assume the build succeeded.
    pause
    exit /b 4
)
echo.
echo Build succeeded on this Windows PC. Opening Unreal Editor...
start "" "%UE_EDITOR%" "%CD%\BuggySensorViz.uproject"
exit /b 0
