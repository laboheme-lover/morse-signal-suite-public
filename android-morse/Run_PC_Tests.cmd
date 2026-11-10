@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "WABUN_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
"%WABUN_PYTHON%" tools\test_core.py
if errorlevel 1 goto done
"%WABUN_PYTHON%" tools\make_test_audio.py
if errorlevel 1 goto done
"%WABUN_PYTHON%" tools\build.py assembleDebug assembleDebugAndroidTest lintDebug
:done
pause
