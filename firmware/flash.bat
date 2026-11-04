@echo off
rem Flash the ready-made firmware to an ESP32 DevKit over USB.
rem   usage:  flash.bat COM5
rem Needs Python + esptool:  pip install esptool
rem Find the COM port in Device Manager -> Ports (COM & LPT) after plugging in the board
rem (install the CP210x or CH340 USB driver if no port appears).
setlocal
cd /d "%~dp0"
if "%~1"=="" (echo usage: flash.bat COMx & exit /b 1)
for %%f in (bin\woolwash_esp32_*.merged.bin) do set BIN=%%f
if not defined BIN (echo No firmware in bin\ - run build.bat first & exit /b 1)
echo Flashing %BIN% to %1 ...
python -m esptool --chip esp32 --port %1 --baud 460800 write_flash 0x0 "%BIN%" || (
  echo If it fails: hold the BOOT button on the board while it says "Connecting...". & exit /b 1)
echo.
echo Done. Open a serial monitor at 115200 baud, or just connect your phone to
echo Wi-Fi "WoolWash-Setup-xxxx" (password woolwash123) and open http://192.168.4.1
pause
