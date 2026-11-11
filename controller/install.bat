@echo off
cd /d "%~dp0\.."
py -m pip install -r controller\requirements.txt
pause
