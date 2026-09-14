@echo off
title AI Attendance System - Windows Autostart Setup
echo ======================================================================
echo    Configuring AI Attendance System to Auto-Start with Windows...
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%SCRIPT_DIR%run_attendance_background.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\AttendanceSystemBackend.lnk"

echo Project Directory: %SCRIPT_DIR%
echo Target Launcher:   %VBS_PATH%
echo Startup Directory: %STARTUP_DIR%
echo.

:: Create shortcut via PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_PATH%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'AI Attendance System Background Backend Server'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [SUCCESS] Autostart successfully configured!
    echo Shortcut created in Windows Startup folder:
    echo   %SHORTCUT_PATH%
    echo.
    echo The Python backend server will now start automatically whenever Windows boots or you log in.
) else (
    echo [ERROR] Failed to create shortcut in Startup folder.
)

echo.
echo Press any key to exit...
pause >nul
