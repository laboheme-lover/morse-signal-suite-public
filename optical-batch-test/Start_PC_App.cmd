@echo off
cd /d "%~dp0"
"..\outputs\morse-ai\.venv\Scripts\python.exe" -m streamlit run "pc\app.py" --server.port 8503 --server.address 127.0.0.1 --server.maxUploadSize 2048
pause
