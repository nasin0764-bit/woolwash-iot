@echo off
rem Starts the WoolWash-IoT autopilot watchdog in its own window.
rem It waits until this Claude session is idle (20 min), then resumes it unattended.
rem To stop: create a file named STOP in this folder, or close the window.
cd /d "%~dp0"
if exist STOP del STOP
start "WoolWash autopilot" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autopilot.ps1" %*
