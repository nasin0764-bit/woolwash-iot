// ---- edit for your site ---------------------------------------------------
#pragma once

#define WIFI_SSID      "YOUR_WIFI"
#define WIFI_PASS      "YOUR_PASSWORD"
#define MACHINE_ID     "WW-01"

// Transport: 1 = HTTP POST to server, 0 = MQTT
#define USE_HTTP       1
#define SERVER_URL     "http://192.168.1.10:8000/api/telemetry"
#define DEVICE_TOKEN   "changeme"
#define MQTT_HOST      "192.168.1.10"
#define MQTT_PORT      1883

#define PERIOD_MS      2000      // telemetry interval

// ---- sensor presence (set 0 if not installed) ------------------------------
#define N_BOWLS        5
#define HAS_LEVEL      1         // JSN-SR04T waterproof ultrasonic, one per bowl
#define HAS_TURBIDITY  1         // analog turbidity probes on bowls 1 and 2
#define HAS_PZEM       1         // PZEM-004T v3 power meter
#define HAS_FLOW       1         // fresh-water inlet flow meter
#define HAS_DRUM_HALL  1         // Hall sensor + magnet on squeeze drum
#define HAS_FEED_SCALE 0         // HX711 belt / hopper scale (optional)

// ---- calibration ------------------------------------------------------------
#define BOWL_DEPTH_CM      80.0  // distance sensor -> bowl bottom
#define FLOW_PULSES_PER_L  450.0 // YF-B6/YF-DN50: see datasheet, verify with bucket test
#define DRUM_MAGNETS       1     // magnets per drum revolution
#define TURB_V_CLEAR       2.50  // probe output in clean water (after divider), V
#define TURB_NTU_PER_V    -1500  // slope, calibrate with formazin standards
#define FEED_KG_H_DEFAULT  425.0 // used when no scale is installed (operator setpoint)
