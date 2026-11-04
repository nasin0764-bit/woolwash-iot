# WoolWash-IoT

IoT monitoring + hybrid soft sensor for the resource-saving wool washing machine
(R.B. Tuguzbayeva, PhD dissertation, TTYSI 2024).

```
WoolWash-IoT/
├─ firmware/woolwash_esp32/   ESP32 sensor node (Arduino) – edit config.h
├─ server/                    FastAPI server: ingest, SQLite, soft sensor, alarms, KPIs, CSV, WebSocket
├─ app/                       Web + mobile app (installable PWA), English / Russian
├─ simulator/                 Digital-twin simulator (same payload as the ESP32, tagged "sim")
├─ paper/                     IEEE IoT Journal draft (IEEEtran LaTeX) – results are TODO until field data exist
├─ docs/HARDWARE.md           Parts list, wiring, installation, field measurement protocol
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

### Real machine
See `docs/HARDWARE.md`. Set `WW_TOKEN` (same as `DEVICE_TOKEN` in `config.h`) before starting the server
on a real network. Optional MQTT: run Mosquitto and set `WW_MQTT_HOST=localhost`.

## API
| Method | Path | |
|---|---|---|
| POST | /api/telemetry | device data (header `X-Token`) |
| GET | /api/machines, /api/latest/{id}, /api/history/{id}?minutes= | data |
| POST | /api/lab | `{machine, moisture_pct, note}` – oven-dry sample, refits soft sensor |
| GET/PUT | /api/model/{id}, /api/geometry/{id} | soft-sensor info, machine geometry |
| GET | /api/export/{id}.csv?hours= | CSV for analysis / paper |
| WS | /ws | live stream |

## Simulator options
```
python simulate.py --speed 60 --lab-every 30 --fault heater:3@1800 --fault drum@3600
```
Faults: `heater:<bowl>`, `leak:<bowl>`, `drum` at simulated second N.

> **Research integrity:** simulator output is for testing software only. Results in the dissertation or the
> journal paper must come from measurements on the real machine (rows with `source = device`).
