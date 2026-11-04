@echo off
rem Reproducible firmware build with arduino-cli (pinned versions).
rem Output: firmware\bin\woolwash_esp32_<ver>.merged.bin  (flash at 0x0)
rem         firmware\bin\woolwash_esp32_<ver>.bin         (app only, for OTA / Arduino IDE)
setlocal
cd /d "%~dp0"
where arduino-cli >nul 2>nul && (set CLI=arduino-cli) || (set CLI=%USERPROFILE%\arduino-cli\arduino-cli.exe)

rem Versions used for the published binaries (firmware 1.1.0):
rem   arduino-cli 1.1.1, esp32:esp32 3.3.12, OneWire 2.3.8, DallasTemperature 4.0.6,
rem   ArduinoJson 7.4.3, PubSubClient 2.8, PZEM004Tv30 1.2.1, HX711 0.6.6
"%CLI%" config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
"%CLI%" core update-index
"%CLI%" core install esp32:esp32@3.3.12
"%CLI%" lib install OneWire@2.3.8 DallasTemperature@4.0.6 ArduinoJson@7.4.3 PubSubClient@2.8 PZEM004Tv30@1.2.1 HX711@0.6.6

"%CLI%" compile --fqbn esp32:esp32:esp32 --export-binaries --output-dir build woolwash_esp32 || exit /b 1
if not exist bin mkdir bin
for /f "tokens=3 delims= " %%v in ('findstr /c:"#define FW_VERSION" woolwash_esp32\config.h') do set VER=%%~v
copy /y build\woolwash_esp32.ino.merged.bin bin\woolwash_esp32_%VER%.merged.bin
copy /y build\woolwash_esp32.ino.bin        bin\woolwash_esp32_%VER%.bin
echo.
echo Built firmware %VER% -> firmware\bin
