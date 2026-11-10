@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0video_app.py" --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false
pause
