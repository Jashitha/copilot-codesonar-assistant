@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================================
echo CodeSonar Assistant - Setup
echo ============================================================

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    exit /b 1
)

set "PYTHON_CMD=py -3"
where py >nul 2>nul || set "PYTHON_CMD=python"

echo Using Python launcher: %PYTHON_CMD%

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create .venv. Install Python 3 first.
        exit /b 1
    )
)

echo Installing dependencies...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    copy ".env.example" ".env" >nul
    if errorlevel 1 (
        echo ERROR: Could not create .env from .env.example.
        exit /b 1
    )
    echo Created .env from .env.example
) else (
    echo .env already exists
)

echo.
echo Setup complete.
echo Next:
echo   1. Edit .env with your project values.
echo   2. Run run.bat for the guided menu.
echo.
pause