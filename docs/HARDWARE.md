# Hardware installation guide – WoolWash-IoT sensor node

> ⚠️ **Safety:** The machine has mains-powered motors and hot (60 °C) alkaline liquor.
> All mains wiring (the PZEM-004T current transformer and the 220/380 V supply) must be done by a
> qualified electrician with the machine **locked out**. The ESP32 box needs its own 5 V DIN-rail
> supply and an IP65 enclosure.

## 1. Bill of materials (one machine, approx. prices)

| # | Part | Qty | Purpose | ≈ USD |
|---|------|-----|---------|------|
| 1 | ESP32 DevKit V1 (ESP-WROOM-32) | 1 | controller + Wi-Fi | 6 |
| 2 | DS18B20 waterproof probe, **stainless sheath, 3 m cable** | 5 | bowl liquor temperature | 15 |
| 3 | JSN-SR04T waterproof ultrasonic sensor | 5 | liquor level in each bowl | 25 |
| 4 | Analog turbidity sensor (SEN0189 type) | 2 | liquor dirtiness, bowls 1–2 | 20 |
| 5 | PZEM-004T v3.0 + 100 A split-core CT | 1 (3 for 3-phase) | power & energy | 10–30 |
| 6 | Water flow meter, pulse output (YF-B6 ½" or YF-DN50 for 2") | 1 | fresh-water make-up | 10–40 |
| 7 | A3144 Hall sensor + neodymium magnet (or NJK-5002C proximity) | 1 | squeeze-drum speed ω | 5 |
| 8 | 5 V 2 A DIN-rail PSU (Mean Well HDR-15-5) | 1 | power supply | 10 |
| 9 | IP65 ABS box, cable glands, terminal blocks | 1 | enclosure | 15 |
| 10 | Resistors 10 k / 20 k (dividers), 4.7 k (one-wire pull-up) | — | level shifting | 1 |
| 11 | Shielded 4-core cable | 30 m | sensor wiring | 15 |
| 12 | (optional) HX711 + 50 kg load cells | 4 | feed-hopper scale | 15 |
| 13 | Lab: drying oven 105 °C, analytical balance 0.01 g, sample tins | — | reference moisture | (lab) |

Total ≈ **150–200 USD** without the oven.

## 2. Wiring (ESP32 side)

| Sensor | Sensor pin | ESP32 pin | Note |
|---|---|---|---|
| DS18B20 ×5 (parallel) | DQ (yellow) | GPIO4 | **4.7 kΩ** DQ→3V3; VDD→3V3, GND |
| JSN-SR04T ×5 | TRIG | GPIO5 (shared) | 5 V supply |
|  | ECHO 1..5 | GPIO18, 19, 21, 22, 23 | **divider 10 k / 20 k** (5 V → 3.3 V) |
| Turbidity ×2 | AOUT | GPIO34, GPIO35 | divider 10 k / 20 k; 5 V supply |
| PZEM-004T v3 | TX / RX | GPIO16 (RX2) / GPIO17 (TX2) | 5 V logic is tolerated by PZEM; put a 1 k series resistor on PZEM TX |
| Flow meter | signal | GPIO27 | 5 V supply, divider on signal |
| Hall A3144 | OUT | GPIO26 | 10 k pull-up to 3V3; supply 3V3 |
| HX711 (opt.) | DT / SCK | GPIO25 / GPIO33 | |

## 3. Mounting positions

```
 feed ─► [Bowl 1]─SQ─[Bowl 2]─SQ─[Bowl 3]─SQ─[Bowl 4]─SQ─[Bowl 5]─SQ─► dryer
           T L Tu      T L Tu      T L         T L         T L
 SQ = squeeze device (ribbed drum Ø250 + slat drum + mesh)      Hall on drum shaft of first SQ
 T  = DS18B20 at mid-depth, 10 cm from wall, away from steam inlet
 L  = JSN-SR04T on a bracket above liquor, pointing down, ≥ 25 cm above max level
 Tu = turbidity probe in a side-stream cup (liquor recirculation), not in the wool flow
 Flow meter on fresh-water inlet pipe; PZEM CT on the machine motor feeder in the cabinet
```

## 4. Commissioning

1. Install Arduino IDE 2, add the ESP32 board package, install the libraries listed in the `.ino` header.
2. Edit `config.h` (Wi-Fi, server IP, token, sensor flags) and upload.
3. Open Serial Monitor (115200) – check `DS18B20 probes found: 5`.
4. **Map the probes:** dip one probe at a time in hot water and note which `bowls[i]` rises; relabel cables.
5. **Level:** measure `BOWL_DEPTH_CM` with a tape (sensor face → bottom).
6. **Flow:** fill a 20 L bucket, compare with `water_total_l`, correct `FLOW_PULSES_PER_L`.
7. **Turbidity:** record the voltage in clean water (`TURB_V_CLEAR`) and in 400 / 800 NTU formazin standards → slope.
8. **Drum ω:** compare with a handheld tachometer at 3 speeds.
9. Check that the dashboard shows "device" data (no *SIMULATED* badge).

## 5. Field measurement protocol (this produces the data for the paper)

The paper needs **real, repeatable measurements**. Suggested campaign (at "Oqbo'tayeva Zulxumor" or "Hisori jun"):

| Campaign | What | Duration | Output |
|---|---|---|---|
| A. Baseline | old double-drum squeezer (if still available) with same sensors | ≥ 5 shifts | baseline energy/water per kg, moisture |
| B. Improved machine | proposed machine, rational settings | ≥ 10 shifts | KPIs, sensor time series |
| C. Soft-sensor calibration | lab moisture sample every 30 min (oven 105 °C, 3 replicates) | during B | ≥ 60 labelled samples |
| D. Validation | new samples on different days / spring vs autumn wool | ≥ 20 samples | held-out test set for RMSE, MAE, R² |
| E. Network | log packet loss, latency (server timestamps), Wi-Fi RSSI | during B | IoT reliability metrics |
| F. Fault detection | deliberately: heater off, low level, drum speed change (safely, supervised) | 1 shift | detection delay, false alarms |

Record for every lab sample: time, bowl/stage, wool type (spring/autumn), wet mass, dry mass, moisture %.
Export CSV from the dashboard (Trends → Export CSV) after every shift and back it up.

## 6. Recording validation data (`docs/IEEE_IoT_Factory_Validation_Template.xlsx`)

| Template sheet | Where the data comes from | How |
|---|---|---|
| Sensor calibration | Lab oven-dry moisture (reference) vs soft-sensor prediction made **before** that sample was used for training | automatic: `tools/fill_template.py` |
| Sensor calibration (temperature, level, flow, ω) | Reference thermometer / tape / bucket / tachometer vs IoT reading | enter by hand during commissioning (§4) |
| Packet delivery | Every packet carries `seq`, `boot_id`, `tx_ms`; server stores `rx_ms`; gaps = lost packets | automatic: `tools/fill_template.py` |
| Water energy batches | Physical water meter and kWh meter readings, weighed wool batch mass | by hand (meters are the reference) |

```
python tools/fill_template.py docs/IEEE_IoT_Factory_Validation_Template.xlsx results/trial_A.xlsx ^
       --machine WW-01 --hours 8 --trial A-2026-11-10
```
Latency is only valid when the ESP32 (NTP) and the server PC are both clock-synchronised; check that the
template's "Negative latencies" count is 0. The script refuses simulated data unless `--allow-sim` is given.
