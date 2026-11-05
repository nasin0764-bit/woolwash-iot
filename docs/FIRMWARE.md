# ESP32 firmware: flash, set up, build

Board: **ESP32 DevKit V1 (ESP-WROOM-32, 4 MB flash)**. Source: `firmware/woolwash_esp32/`.

## A. Flash the ready-made firmware (no Arduino needed)

Ready-made files are in `firmware/bin/`:

| File | Use |
|---|---|
| `woolwash_esp32_<ver>.merged.bin` | **complete image, flash at address 0x0** (normal use) |
| `woolwash_esp32_<ver>.bin` | application only (Arduino IDE / OTA updates) |

**Option 1: browser (Chrome or Edge, easiest)**
1. Plug the ESP32 into the PC with a USB **data** cable. If Windows shows no new COM port, install the
   CP210x or CH340 driver (the chip name is printed next to the USB socket).
2. Open https://espressif.github.io/esptool-js/ → *Connect* → choose the port.
3. Flash address **0x0**, file `woolwash_esp32_<ver>.merged.bin` → *Program*.
   (If it does not connect: hold the **BOOT** button while clicking Connect.)

**Option 2: command line**
```
pip install esptool
firmware\flash.bat COM5        (use your port)
```

## B. First-time setup (on site, with a phone)

1. Power the board. The blue LED **blinks** = setup mode.
2. On the phone, connect to Wi-Fi **`WoolWash-Setup-xxxx`**, password **`woolwash123`**.
3. The setup page opens automatically (or open **http://192.168.4.1**). Enter:
   - Wi-Fi name and password of the plant network
   - Server URL, e.g. `http://192.168.1.10:8000/api/telemetry` (IP of the PC running `start_server.bat`)
   - Device token (same as `WW_TOKEN` of the server, default `changeme`)
   - Machine ID, e.g. `WW-01`
   - MQTT host: leave **empty** to use HTTP
4. *Save and restart*. The LED turns **on** each time a message is accepted by the server.
5. Live readings for calibration: open `http://<board-IP>/` on the plant network (the IP is shown
   in the router, or in the serial monitor at 115200 baud). The page refreshes every 3 s.

**Change settings later:** hold **BOOT** while plugging in power, keep holding for 3 s → settings cleared →
setup mode again. If the stored Wi-Fi is unreachable, the board opens the setup portal for 5 min and then
retries automatically.

## C. Build from source

**Arduino IDE 2**
1. *File → Preferences → Additional boards manager URLs*:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. *Boards Manager* → install **esp32 by Espressif, version 3.3.12** (version used for the published binaries).
3. *Library Manager* → install **OneWire, DallasTemperature, ArduinoJson (7.x), PubSubClient,
   PZEM004Tv30** by Jakub Mandula (and HX711 only if `HAS_FEED_SCALE 1`).
4. Open `firmware/woolwash_esp32/woolwash_esp32.ino`, board **ESP32 Dev Module**, *Tools → Flash Mode → **DIO***, upload.
   (DIO works with every ESP32 flash chip and in Espressif QEMU; the default QIO crashed at flash init in the emulator.)

**Command line (reproducible, pinned versions):** `firmware\build.bat` → writes `firmware\bin\`.

Sensor flags and calibration constants are in `config.h` (rebuild after changing them). Wi-Fi and
server settings are **not** compiled in. They are stored in the ESP32 flash by the setup page.

## C2. Emulator boot test
`powershell -ExecutionPolicy Bypass -File firmware\qemu_boot_test.ps1` boots the image in Espressif QEMU.
Result for 1.1.0 (DIO): bootloader, banner and sensor scan pass; the run then stops at Wi-Fi start
(`esp_phy_enable`), as expected, because QEMU has no Wi-Fi radio.

## D. Message format (one JSON per 2 s)

```json
{"machine_id":"WW-01","source":"device","fw":"1.1.0","ts":1793800000,"seq":42,"boot_id":123456,
 "tx_ms":1793800000123,"rssi":-61,
 "bowls":[{"id":1,"temp_c":59.8,"level_cm":60.1,"turbidity_ntu":410}, ...],
 "squeeze":[{"stage":1,"drum_omega":16.02}],
 "water_lpm":0,"water_total_l":1234.5,"power_w":4210,"energy_kwh":12.3,
 "feed_kg_h":425,"feed_total_kg":1020.5}
```
`seq`/`boot_id`/`tx_ms` feed the packet-delivery and latency analysis (`tools/fill_template.py`).
