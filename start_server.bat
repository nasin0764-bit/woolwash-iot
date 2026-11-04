@echo off
cd /d "%~dp0server"
if "%WW_TOKEN%"=="" set WW_TOKEN=changeme
echo WoolWash server: http://localhost:8000
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
