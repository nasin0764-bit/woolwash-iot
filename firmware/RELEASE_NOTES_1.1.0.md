**Pre-release: compiled and checked, not yet tested on a physical board.**

### Firmware 1.1.0 (ESP32 DevKit V1 / ESP-WROOM-32, 4 MB)
- `woolwash_esp32_1.1.0.merged.bin`: complete image, **flash at 0x0**
  (browser: https://espressif.github.io/esptool-js/ or `firmware\flash.bat COM5`)
- `woolwash_esp32_1.1.0.bin`: application only
- `SHA256SUMS.txt`: checksums

**First start:** connect to Wi-Fi `WoolWash-Setup-xxxx` (password `woolwash123`), open http://192.168.4.1, and
enter the plant Wi-Fi, server URL, token and machine ID. Hold BOOT for 3 s at power-on to reset the settings.
Details: `docs/FIRMWARE.md`.

Built with arduino-cli 1.1.1 and esp32:esp32 3.3.12 (OneWire 2.3.8, DallasTemperature 4.0.6, ArduinoJson 7.4.3,
PubSubClient 2.8, PZEM004Tv30 1.2.1, HX711 0.6.6).

### Also in this version
- Server: staged soft sensor with plant-offset shrinkage; dirty-liquor advisory with debounce, hysteresis and
  per-machine limits (`/api/limits`); validation exports for the IEEE template
- Tools: `fill_template.py`, `analyze_field.py` (Section VII tables), `sim_study.py`, `make_forms.py`
- Tests: 21 pytest tests
- Docs: Russian and Uzbek guides, printable data-collection forms
