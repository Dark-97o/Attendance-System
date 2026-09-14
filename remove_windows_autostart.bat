@echo off
title AI Attendance System - Remove Windows Autostart
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AttendanceSystemBackend.lnk"

if exist "%SHORTCUT_PATH%" (
    del /f /q "%SHORTCUT_PATH%"
    echo [SUCCESS] Removed Attendance System from Windows Startup folder.
) else (
    echo [INFO] No autostart shortcut found in Startup folder.
)

echo.
pause
