@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\start_emulator.py --visible
pause
