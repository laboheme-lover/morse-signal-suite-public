@echo off
cd /d "%~dp0"
"..\outputs\morse-ai\.venv\Scripts\python.exe" -m streamlit run app.py --server.port 8504 --server.address 127.0.0.1
