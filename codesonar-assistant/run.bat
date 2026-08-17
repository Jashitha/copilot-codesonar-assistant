@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv is missing.
    echo Run setup.bat first.
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

:menu
cls
echo ============================================================
echo CodeSonar Assistant
echo ============================================================
echo 1^) Update Tracker
echo 2^) Open Dashboard
echo 3^) Preview Daily CodeSonar Report
echo 4^) Send Daily CodeSonar Report
echo 5^) Ask the assistant a question
echo Q^) Quit
echo.
choice /c 12345Q /n /m "Select an option: "

if errorlevel 6 goto :eof
if errorlevel 5 goto :ask
if errorlevel 4 goto :send_report
if errorlevel 3 goto :preview_report
if errorlevel 2 goto :open_dashboard
if errorlevel 1 goto :update_tracker

goto :menu

:update_tracker
echo.
"%PYTHON%" scripts\codesonar_assistant.py --query "Update Tracker"
echo.
pause
goto :menu

:open_dashboard
echo.
if not exist "output\dashboard\index.html" (
    echo Dashboard not found yet. Running Update Tracker first...
    "%PYTHON%" scripts\codesonar_assistant.py --query "Update Tracker"
)
start "" "output\dashboard\index.html"
echo.
pause
goto :menu

:preview_report
echo.
"%PYTHON%" scripts\run_daily_code_sonar_report.py --preview
echo.
pause
goto :menu

:send_report
echo.
"%PYTHON%" scripts\run_daily_code_sonar_report.py
echo.
pause
goto :menu

:ask
echo.
set /p USER_QUERY=Enter your question: 
if "%USER_QUERY%"=="" goto :menu
echo.
"%PYTHON%" scripts\codesonar_assistant.py --query "%USER_QUERY%" --format text
echo.
pause
goto :menu