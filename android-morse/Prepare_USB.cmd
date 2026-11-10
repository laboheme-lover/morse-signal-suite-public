@echo off
setlocal
cd /d "%~dp0"
if not exist "%USERPROFILE%\.android" mkdir "%USERPROFILE%\.android"
if not exist "%USERPROFILE%\.android" (
  echo Could not create Android preferences folder.
  pause
  exit /b 1
)
".toolchain\sdk\platform-tools\adb.exe" start-server
".toolchain\sdk\platform-tools\adb.exe" devices -l
echo.
echo Allow USB debugging on your phone if requested.
echo Then return to Codex.
pause
