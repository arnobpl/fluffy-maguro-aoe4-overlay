@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%src"
set "VENV_DIR=%ROOT%venv"
set "SCRIPT=%APP_DIR%\AoE4_Overlay.py"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW=%VENV_DIR%\Scripts\pythonw.exe"
set "REQUIREMENTS=%ROOT%requirements.txt"

if not exist "%SCRIPT%" (
    echo [AoE4 Overlay] App script not found: "%SCRIPT%"
    pause
    exit /b 1
)

if not exist "%REQUIREMENTS%" (
    echo [AoE4 Overlay] Requirements file not found: "%REQUIREMENTS%"
    pause
    exit /b 1
)

call :EnsureVenv || exit /b 1

if not exist "%PYTHON%" (
    echo [AoE4 Overlay] Virtual environment is missing python.exe: "%PYTHON%"
    pause
    exit /b 1
)

if not exist "%PYTHONW%" (
    echo [AoE4 Overlay] Virtual environment is missing pythonw.exe: "%PYTHONW%"
    pause
    exit /b 1
)

if defined VENV_NEEDS_INSTALL (
    echo [AoE4 Overlay] Installing Python dependencies...
    "%PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 (
        pause
        exit /b 1
    )

    "%PYTHON%" -m pip install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        pause
        exit /b 1
    )

    echo [AoE4 Overlay] Setup complete. Starting app...
)

start "" "%PYTHONW%" "%SCRIPT%"
exit /b 0

:EnsureVenv
if exist "%PYTHON%" (
    call :CheckVenvHealth
    if not errorlevel 1 exit /b 0
)

echo [AoE4 Overlay] Creating local virtual environment...
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
call :CreateVenv || exit /b 1
set "VENV_NEEDS_INSTALL=1"
exit /b 0

:CheckVenvHealth
if not exist "%PYTHONW%" exit /b 1
"%PYTHON%" -c "import appdirs, keyboard, PyQt5, requests, urllib3, websockets" >nul 2>nul
exit /b %errorlevel%

:CreateVenv
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv "%VENV_DIR%"
    exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m venv "%VENV_DIR%"
    exit /b %errorlevel%
)

echo [AoE4 Overlay] Python 3 is required. Install Python or make sure 'py' or 'python' is available on PATH.
pause
exit /b 1
