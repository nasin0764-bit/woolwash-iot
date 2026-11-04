@echo off
cd /d "%~dp0simulator"
python simulate.py --speed 60 --lab-every 30 --fault heater:3@3600
pause
