@echo off
rem Run the command-line version with the local venv created by setup_venv.bat.
setlocal
set "VENV=%LOCALAPPDATA%\crack-thickness\.venv"
if not exist "%VENV%\Scripts\python.exe" (
    call "%~dp0setup_venv.bat" || (pause & exit /b 1)
)
set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\crack-thickness\pycache"
"%VENV%\Scripts\python.exe" "%~dp0crack_thickness_from_images.py"
pause
