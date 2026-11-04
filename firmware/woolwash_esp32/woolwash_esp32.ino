/*
  WoolWash-IoT – ESP32 sensor node for the resource-saving wool washing machine.
  Board: ESP32 DevKit V1 (Arduino core 2.x / 3.x)

  Libraries (Arduino Library Manager):
    OneWire, DallasTemperature, ArduinoJson (v7), PubSubClient,
    PZEM004Tv30 (mandulaj), HX711 (bogde) – only if HAS_FEED_SCALE

  Pin map (see docs/HARDWARE.md for wiring and level shifting):
    GPIO4         DS18B20 one-wire bus (5 probes, 4.7k pull-up to 3V3)
    GPIO5         JSN-SR04T TRIG (shared by all 5)
    GPIO18,19,21,22,23  JSN-SR04T ECHO bowl 1..5  (5V -> 3V3 divider!)
    GPIO16/17     PZEM-004T RX/TX (UART2)
    GPIO27        flow meter pulse
    GPIO26        drum Hall sensor (A3144 / NJK-5002C)
    GPIO34,35     turbidity bowl 1, 2 (ADC1; divider 5V->3V3)
    GPIO25/33     HX711 DT/SCK (optional)
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>
#include "config.h"
#if HAS_PZEM
#include <PZEM004Tv30.h>
#endif
#if HAS_FEED_SCALE
#include <HX711.h>
#endif

#define PIN_ONEWIRE 4
#define PIN_TRIG    5
const uint8_t PIN_ECHO[5] = {18, 19, 21, 22, 23};
#define PIN_FLOW    27
#define PIN_HALL    26
const uint8_t PIN_TURB[2] = {34, 35};

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
DeviceAddress probe[N_BOWLS];   // order: sorted by address – map once with docs/HARDWARE.md §4
uint8_t nProbes = 0;

#if HAS_PZEM
PZEM004Tv30 pzem(Serial2, 16, 17);
#endif
#if HAS_FEED_SCALE
HX711 scale;
#endif

WiFiClient net;
PubSubClient mqtt(net);

volatile uint32_t flowPulses = 0, hallPulses = 0;
volatile uint32_t lastHallUs = 0, hallPeriodUs = 0;
void IRAM_ATTR onFlow() { flowPulses++; }
void IRAM_ATTR onHall() {
  uint32_t now = micros();
  if (now - lastHallUs > 2000) { hallPeriodUs = now - lastHallUs; lastHallUs = now; hallPulses++; }
}

double waterTotalL = 0, feedTotalKg = 0, energyKwh0 = -1;
uint32_t lastSend = 0;

void wifiUp() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED) configTime(5 * 3600, 0, "pool.ntp.org");  // UTC+5 Tashkent
}

float readLevelCm(uint8_t i) {
  digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(4);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(20);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long us = pulseIn(PIN_ECHO[i], HIGH, 30000UL);
  if (us == 0) return NAN;
  float dist = us * 0.0343f / 2.0f;              // cm (speed of sound in warm humid air ≈ 343 m/s)
  return BOWL_DEPTH_CM - dist;
}

float readTurbidity(uint8_t i) {
  uint32_t acc = 0;
  for (int k = 0; k < 32; k++) acc += analogReadMilliVolts(PIN_TURB[i]);
  float v = acc / 32.0f / 1000.0f;
  float ntu = (v - TURB_V_CLEAR) * TURB_NTU_PER_V;
  return ntu < 0 ? 0 : ntu;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  for (uint8_t i = 0; i < 5; i++) pinMode(PIN_ECHO[i], INPUT);
  pinMode(PIN_FLOW, INPUT_PULLUP);
  pinMode(PIN_HALL, INPUT_PULLUP);
  attachInterrupt(PIN_FLOW, onFlow, FALLING);
  attachInterrupt(PIN_HALL, onHall, FALLING);
  analogSetAttenuation(ADC_11db);

  ds.begin();
  ds.setResolution(11);
  ds.setWaitForConversion(false);
  nProbes = min<uint8_t>(ds.getDeviceCount(), N_BOWLS);
  for (uint8_t i = 0; i < nProbes; i++) ds.getAddress(probe[i], i);
  Serial.printf("DS18B20 probes found: %d\n", nProbes);

#if HAS_FEED_SCALE
  scale.begin(25, 33);
  scale.set_scale(1.0f);   // calibrate: known mass / raw reading
#endif
  wifiUp();
#if !USE_HTTP
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(1024);
#endif
  ds.requestTemperatures();
}

void loop() {
#if !USE_HTTP
  if (!mqtt.connected()) mqtt.connect(MACHINE_ID);
  mqtt.loop();
#endif
  uint32_t now = millis();
  if (now - lastSend < PERIOD_MS) return;
  float dt = (now - lastSend) / 1000.0f;
  lastSend = now;
  wifiUp();

  JsonDocument doc;
  doc["machine_id"] = MACHINE_ID;
  doc["source"] = "device";
  time_t ts; time(&ts); doc["ts"] = (double)ts;   // server substitutes its time if NTP not synced

  JsonArray bowls = doc["bowls"].to<JsonArray>();
  for (uint8_t i = 0; i < N_BOWLS; i++) {
    JsonObject b = bowls.add<JsonObject>();
    b["id"] = i + 1;
    if (i < nProbes) {
      float t = ds.getTempC(probe[i]);
      if (t > -100) b["temp_c"] = round(t * 100) / 100.0;
    }
#if HAS_LEVEL
    float lv = readLevelCm(i);
    if (!isnan(lv)) b["level_cm"] = round(lv * 10) / 10.0;
    delay(60);   // let echoes die out before the next sensor
#endif
#if HAS_TURBIDITY
    if (i < 2) b["turbidity_ntu"] = round(readTurbidity(i));
#endif
  }
  ds.requestTemperatures();   // non-blocking; read next cycle

  // squeeze drum angular speed
  noInterrupts();
  uint32_t per = hallPeriodUs, lastUs = lastHallUs;
  interrupts();
  float omega = 0;
  if (per > 0 && (micros() - lastUs) < 2000000UL) omega = 2.0f * PI / (per * 1e-6f * DRUM_MAGNETS);
  JsonArray sq = doc["squeeze"].to<JsonArray>();
  JsonObject s = sq.add<JsonObject>();
  s["stage"] = 1;
#if HAS_DRUM_HALL
  s["drum_omega"] = round(omega * 1000) / 1000.0;
#endif

#if HAS_FLOW
  noInterrupts(); uint32_t fp = flowPulses; flowPulses = 0; interrupts();
  float litres = fp / FLOW_PULSES_PER_L;
  waterTotalL += litres;
  doc["water_lpm"] = round(litres / dt * 60 * 100) / 100.0;
  doc["water_total_l"] = round(waterTotalL * 10) / 10.0;
#endif

#if HAS_PZEM
  float p = pzem.power(), e = pzem.energy();
  if (!isnan(p)) doc["power_w"] = p;
  if (!isnan(e)) { if (energyKwh0 < 0) energyKwh0 = e; doc["energy_kwh"] = e - energyKwh0; }
#endif

  float feed = FEED_KG_H_DEFAULT;
#if HAS_FEED_SCALE
  // replace with belt-scale throughput computation for your conveyor
  feed = scale.get_units(5);
#endif
  feedTotalKg += feed * dt / 3600.0;
  doc["feed_kg_h"] = feed;
  doc["feed_total_kg"] = round(feedTotalKg * 100) / 100.0;

  String body;
  serializeJson(doc, body);
#if USE_HTTP
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(net, SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Token", DEVICE_TOKEN);
    int code = http.POST(body);
    Serial.printf("POST %d  %s\n", code, code == 200 ? http.getString().c_str() : "");
    http.end();
  }
#else
  mqtt.publish("woolwash/" MACHINE_ID "/telemetry", body.c_str());
#endif
  Serial.println(body);
}
