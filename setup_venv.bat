@echo off
rem Create/update the virtual environment on the LOCAL disk.
rem The project folder may live on a network drive, where loading numpy/scipy
rem DLLs takes minutes; a local venv starts in seconds.
setlocal
set "VENV=%LOCALAPPDATA%\crack-thickness\.venv"
cd /d "%~dp0"

where uv >nul 2>nul
if %errorlevel%==0 (
    rem uv: Python version from .python-version, pinned versions from uv.lock
    set "UV_PROJECT_ENVIRONMENT=%VENV%"
    uv sync --frozen || goto :fail
) else (
    rem Fallback without uv: plain venv + pip (unpinned versions)
    if not exist "%VENV%\Scripts\python.exe" (
        py -3 -m venv "%VENV%" || python -m venv "%VENV%" || goto :fail
    )
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
    "%VENV%\Scripts\python.exe" -m pip install colorama matplotlib numpy pillow scipy || goto :fail
)

echo.
echo Environment ready: %VENV%
echo Start the GUI with run_gui.bat
exit /b 0

:fail
echo.
echo Setup failed.
exit /b 1
