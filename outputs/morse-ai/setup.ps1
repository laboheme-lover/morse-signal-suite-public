$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3.11 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required. Install it and retry.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
