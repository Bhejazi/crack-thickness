@echo off
rem Launch the GUI with the local venv created by setup_venv.bat.
setlocal
set "VENV=%LOCALAPPDATA%\crack-thickness\.venv"
if not exist "%VENV%\Scripts\pythonw.exe" (
    call "%~dp0setup_venv.bat" || (pause & exit /b 1)
)
rem Keep bytecode caches local too, not on the network drive.
set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\crack-thickness\pycache"
start "" "%VENV%\Scripts\pythonw.exe" "%~dp0crack_thickness_gui.py"
