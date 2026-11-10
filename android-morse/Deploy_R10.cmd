@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "WABUN_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%WABUN_PYTHON%" (
  echo Python runtime not found. See docs.
  pause
  exit /b 1
)
"%WABUN_PYTHON%" tools\deploy.py --test %*
pause
