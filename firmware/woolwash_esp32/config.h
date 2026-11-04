// ---------------------------------------------------------------------------
//  WoolWash-IoT firmware configuration
//
//  Wi-Fi, server URL, token and machine ID are NOT compiled in any more.
//  They are entered once in the setup portal (Wi-Fi "WoolWash-Setup-xxxx",
//  then open http://192.168.4.1) and stored in the ESP32 flash (NVS).
//  Hold the BOOT button for 3 s while powering on to clear them.
//
//  The values below are only the DEFAULTS pre-filled in the portal form,
//  plus sensor flags and calibration constants (change + recompile if needed).
// ---------------------------------------------------------------------------
#pragma once

#define FW_VERSION         "1.1.0"

// ---- portal defaults --------------------------------------------------------
#define DEFAULT_SERVER_URL "http://192.168.1.10:8000/api/telemetry"
#define DEFAULT_TOKEN      "changeme"
#define DEFAULT_MACHINE_ID "WW-01"
#define DEFAULT_MQTT_HOST  ""          // empty = use HTTP
#define DEFAULT_MQTT_PORT  1883
#define SETUP_AP_PASSWORD  "woolwash123"  // password of the setup Wi-Fi (min 8 chars)

#define PERIOD_MS          2000        // telemetry interval

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
