@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m streamlit run evaluation_app.py --server.address 127.0.0.1 --server.port 8503
pause
