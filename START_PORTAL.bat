@echo off
title AI Attendance Portal Launcher
echo ======================================================================
echo    Starting AI Attendance System (Raspberry Pi 5 / PC Architecture)
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check if port 8080 is already open
powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue).Count" > %temp%\port_check.txt
set /p PORT_COUNT=<%temp%\port_check.txt
del %temp%\port_check.txt 2>nul

if "%PORT_COUNT%"=="0" (
    echo [INFO] Launching Python backend server on port 8080...
    start /b "" python run.py
    timeout /t 3 /nobreak >nul
) else (
    echo [INFO] Backend is already running on port 8080.
)

echo.
echo [INFO] Opening Web Dashboard at http://localhost:8080...
start http://localhost:8080
echo.
echo System is active. You can minimize or close this launcher window.
timeout /t 4 >nul
exit
