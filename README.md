# WoolWash-IoT

IoT monitoring + hybrid soft sensor for the resource-saving wool washing machine
(R.B. Tuguzbayeva, PhD dissertation, TTYSI 2024).

```
WoolWash-IoT/
├─ firmware/
│  ├─ woolwash_esp32/         ESP32 sensor node source (Arduino) – sensor flags in config.h
│  ├─ bin/                    READY-MADE firmware: *.merged.bin (flash at 0x0) + SHA256SUMS.txt
│  ├─ build.bat               reproducible build with arduino-cli (pinned versions)
│  └─ flash.bat               flash over USB:  flash.bat COM5
├─ server/                    FastAPI server: ingest, SQLite, soft sensor, alarms, KPIs, CSV, WebSocket
├─ app/                       Web + mobile app (installable PWA), English / Russian
├─ simulator/                 Digital-twin simulator (same payload as the ESP32, tagged "sim")
├─ tools/
│  ├─ fill_template.py        fills docs/IEEE_IoT_Factory_Validation_Template.xlsx from the server
│  └─ sim_study.py            simulation + bench study for the paper (results/sim_study, paper/figs)
├─ results/sim_study/         outputs of sim_study.py (JSON)
├─ paper/                     IEEE IoT Journal manuscript (IEEEtran LaTeX), cover letter, photos
├─ docs/
│  ├─ FIRMWARE.md             flash, Wi-Fi setup portal, build from source, message format
│  ├─ HARDWARE.md             parts list, wiring, installation, field measurement protocol
│  └─ IEEE_IoT_Factory_Validation_Template.xlsx
├─ start_server.bat           start the server
└─ start_simulator.bat        start the simulator (fast mode, with lab samples)
```

## Quick start (Windows)

1. Once: `pip install fastapi "uvicorn[standard]" paho-mqtt numpy`
2. Double-click **start_server.bat** → open http://localhost:8000
3. Double-click **start_simulator.bat** → live data appears (orange *SIMULATED DATA* badge).

### Mobile app
Phone on the same Wi-Fi → open `http://<PC-IP>:8000` (find the IP with `ipconfig`) →
Android Chrome: menu ⋮ → *Install app* · iPhone Safari: Share → *Add to Home Screen*.
For use outside the plant, host the server on a VPS with HTTPS (needed for full PWA features on phones).

### Real machine (ESP32)
1. Wire the sensors: `docs/HARDWARE.md`.
2. Flash `firmware/bin/woolwash_esp32_1.1.0.merged.bin` at **0x0**, in the browser via
   https://espressif.github.io/esptool-js/ or with `firmware\flash.bat COM5`. No Arduino install needed.
3. Phone → Wi-Fi **WoolWash-Setup-xxxx** (password `woolwash123`) → http://192.168.4.1 →
   enter plant Wi-Fi, server URL `http://<PC-IP>:8000/api/telemetry`, token, machine ID.
4. Start the server with the same token: `set WW_TOKEN=yourtoken` then `start_server.bat`.

Details: `docs/FIRMWARE.md`. Optional MQTT: run Mosquitto, set `WW_MQTT_HOST=localhost` on the server and the
broker host in the setup page.

## API
| Method | Path | |
|---|---|---|
| POST | /api/telemetry | device data (header `X-Token`) |
| GET | /api/machines, /api/latest/{id}, /api/history/{id}?minutes= | data |
| POST | /api/lab | `{machine, moisture_pct, note}` – oven-dry sample, refits soft sensor |
| GET/PUT | /api/model/{id}, /api/geometry/{id} | soft-sensor info, machine geometry (PUT needs `X-Token`) |
| GET/PUT | /api/limits/{id} | per-machine alarm limits (PUT needs `X-Token`); also in the app tab *Commissioning* |
| GET | /api/export/{id}.csv?hours= | CSV for analysis / paper |
| GET | /api/validation/{id}/packets.csv, /calibration.csv | rows for the IEEE validation template |
| WS | /ws | live stream |

## Simulator options
```
python simulate.py --speed 60 --lab-every 30 --fault heater:3@1800 --fault drum@3600 --loss 0.05
```
Faults: `heater:<bowl>`, `leak:<bowl>`, `drum` at simulated second N; `--loss` drops packets.

## Paper study
`python tools/sim_study.py` reproduces the *Simulation and Bench Study* section (≈10 min).

> **Research integrity:** simulator output is for testing software only. Factory results in the
> journal paper must come from measurements on the real machine (rows with `source = device`).
