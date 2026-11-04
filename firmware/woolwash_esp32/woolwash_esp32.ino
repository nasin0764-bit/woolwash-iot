/*
  WoolWash-IoT – ESP32 sensor node for the resource-saving wool washing machine.
  Board: ESP32 DevKit V1 (ESP-WROOM-32), Arduino-ESP32 core 3.x

  Libraries (Arduino Library Manager):
    OneWire, DallasTemperature, ArduinoJson (v7), PubSubClient,
    PZEM-004T-v30 (mandulaj), HX711 (bogde) – only if HAS_FEED_SCALE

  FIRST START: no Wi-Fi stored -> the board opens Wi-Fi "WoolWash-Setup-xxxx"
  (password in config.h, default woolwash123). Connect with a phone, open
  http://192.168.4.1, enter Wi-Fi, server URL, token and machine ID, Save.
  RESET SETTINGS: hold BOOT (GPIO0) while powering on, for 3 s.
  RUNNING: open http://<board-ip>/ on the same network to see live readings
  (useful during sensor calibration).

  Pin map (see docs/HARDWARE.md for wiring and level shifting):
    GPIO4         DS18B20 one-wire bus (5 probes, 4.7k pull-up to 3V3)
    GPIO5         JSN-SR04T TRIG (shared by all 5)
    GPIO18,19,21,22,23  JSN-SR04T ECHO bowl 1..5  (5V -> 3V3 divider!)
    GPIO16/17     PZEM-004T RX/TX (UART2)
    GPIO27        flow meter pulse
    GPIO26        drum Hall sensor (A3144 / NJK-5002C)
    GPIO34,35     turbidity bowl 1, 2 (ADC1; divider 5V->3V3)
    GPIO25/33     HX711 DT/SCK (optional)
    GPIO0         BOOT button (settings reset)
    GPIO2         on-board LED: blinking = setup portal, on = sending OK
*/
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>
#include <sys/time.h>
#include <esp_random.h>
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
#define PIN_BOOT    0
#define PIN_LED     2

// ---------------------------------------------------------------- settings
struct Settings {
  String ssid, pass, url, token, mid, mqttHost;
  uint16_t mqttPort = DEFAULT_MQTT_PORT;
} cfg;
Preferences prefs;

void loadSettings() {
  prefs.begin("ww", true);
  cfg.ssid     = prefs.getString("ssid", "");
  cfg.pass     = prefs.getString("pass", "");
  cfg.url      = prefs.getString("url", DEFAULT_SERVER_URL);
  cfg.token    = prefs.getString("token", DEFAULT_TOKEN);
  cfg.mid      = prefs.getString("mid", DEFAULT_MACHINE_ID);
  cfg.mqttHost = prefs.getString("mqtt", DEFAULT_MQTT_HOST);
  cfg.mqttPort = prefs.getUShort("mport", DEFAULT_MQTT_PORT);
  prefs.end();
}

void saveSettings() {
  prefs.begin("ww", false);
  prefs.putString("ssid", cfg.ssid);
  prefs.putString("pass", cfg.pass);
  prefs.putString("url", cfg.url);
  prefs.putString("token", cfg.token);
  prefs.putString("mid", cfg.mid);
  prefs.putString("mqtt", cfg.mqttHost);
  prefs.putUShort("mport", cfg.mqttPort);
  prefs.end();
}

void clearSettings() {
  prefs.begin("ww", false);
  prefs.clear();
  prefs.end();
}

// ---------------------------------------------------------------- sensors
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
DeviceAddress probe[N_BOWLS];   // order: by bus enumeration – map once (docs/HARDWARE.md §4)
uint8_t nProbes = 0;

#if HAS_PZEM
PZEM004Tv30 pzem(Serial2, 16, 17);
#endif
#if HAS_FEED_SCALE
HX711 scale;
#endif

WiFiClient net;
PubSubClient mqtt(net);
WebServer web(80);
DNSServer dns;
bool portalMode = false;

volatile uint32_t flowPulses = 0, hallPulses = 0;
volatile uint32_t lastHallUs = 0, hallPeriodUs = 0;
void IRAM_ATTR onFlow() { flowPulses++; }
void IRAM_ATTR onHall() {
  uint32_t now = micros();
  if (now - lastHallUs > 2000) { hallPeriodUs = now - lastHallUs; lastHallUs = now; hallPulses++; }
}

double waterTotalL = 0, feedTotalKg = 0, energyKwh0 = -1;
uint32_t lastSend = 0;
uint32_t txSeq = 0;        // increments on every transmit attempt (gaps at server = lost packets)
uint32_t bootId = 0;       // random per boot, separates sequence counters across restarts
int lastHttpCode = 0;
String lastBody = "{}";

float readLevelCm(uint8_t i) {
  digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(4);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(20);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long us = pulseIn(PIN_ECHO[i], HIGH, 30000UL);
  if (us == 0) return NAN;
  float dist = us * 0.0343f / 2.0f;              // cm
  return BOWL_DEPTH_CM - dist;
}

float readTurbidity(uint8_t i) {
  uint32_t acc = 0;
  for (int k = 0; k < 32; k++) acc += analogReadMilliVolts(PIN_TURB[i]);
  float v = acc / 32.0f / 1000.0f;
  float ntu = (v - TURB_V_CLEAR) * TURB_NTU_PER_V;
  return ntu < 0 ? 0 : ntu;
}

// ---------------------------------------------------------------- web pages
String esc(const String &s) {
  String o; o.reserve(s.length());
  for (char c : s) {
    if (c == '<') o += "&lt;"; else if (c == '>') o += "&gt;";
    else if (c == '"') o += "&quot;"; else if (c == '&') o += "&amp;"; else o += c;
  }
  return o;
}

const char *CSS = "<style>body{font-family:sans-serif;max-width:520px;margin:20px auto;padding:0 14px}"
                  "input{width:100%;padding:8px;margin:4px 0 12px;box-sizing:border-box}"
                  "button{padding:10px 18px;background:#1f5f8b;color:#fff;border:0;border-radius:6px}"
                  "pre{background:#f2f4f6;padding:10px;overflow:auto;font-size:12px}</style>";

void pageSetup() {
  String h = "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>";
  h += CSS;
  h += "<h2>WoolWash-IoT setup</h2><p>Firmware " FW_VERSION "</p><form method=POST action=/save>";
  h += "Wi-Fi name (SSID)<input name=ssid value=\"" + esc(cfg.ssid) + "\" required>";
  h += "Wi-Fi password<input name=pass type=password value=\"" + esc(cfg.pass) + "\">";
  h += "Server URL<input name=url value=\"" + esc(cfg.url) + "\">";
  h += "Device token (same as WW_TOKEN on server)<input name=token value=\"" + esc(cfg.token) + "\">";
  h += "Machine ID<input name=mid value=\"" + esc(cfg.mid) + "\">";
  h += "MQTT broker host (empty = HTTP)<input name=mqtt value=\"" + esc(cfg.mqttHost) + "\">";
  h += "MQTT port<input name=mport type=number value=\"" + String(cfg.mqttPort) + "\">";
  h += "<button type=submit>Save and restart</button></form>";
  web.send(200, "text/html", h);
}

void pageSave() {
  cfg.ssid = web.arg("ssid"); cfg.pass = web.arg("pass"); cfg.url = web.arg("url");
  cfg.token = web.arg("token"); cfg.mid = web.arg("mid"); cfg.mqttHost = web.arg("mqtt");
  cfg.mqttPort = web.arg("mport").toInt() > 0 ? web.arg("mport").toInt() : DEFAULT_MQTT_PORT;
  saveSettings();
  web.send(200, "text/html", String(CSS) + "<h3>Saved. Restarting...</h3><p>Reconnect your phone to the normal Wi-Fi.</p>");
  delay(1500);
  ESP.restart();
}

void pageStatus() {
  String h = "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
             "<meta http-equiv=refresh content=3>";
  h += CSS;
  h += "<h2>WoolWash-IoT node</h2><p>Machine <b>" + esc(cfg.mid) + "</b> &middot; FW " FW_VERSION
       " &middot; RSSI " + String(WiFi.RSSI()) + " dBm &middot; last send code " + String(lastHttpCode) +
       " &middot; seq " + String(txSeq) + "</p><pre>" + esc(lastBody) + "</pre>"
       "<p>Raw JSON: <a href=/json>/json</a>. To change settings: hold BOOT 3 s while powering on.</p>";
  web.send(200, "text/html", h);
}

void startPortal() {
  portalMode = true;
  char ap[32];
  snprintf(ap, sizeof ap, "WoolWash-Setup-%04X", (uint16_t)(ESP.getEfuseMac() & 0xFFFF));
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ap, SETUP_AP_PASSWORD);
  dns.start(53, "*", WiFi.softAPIP());
  web.on("/", pageSetup);
  web.on("/save", HTTP_POST, pageSave);
  web.onNotFound(pageSetup);   // captive portal: any URL shows the form
  web.begin();
  Serial.printf("SETUP PORTAL: Wi-Fi '%s' password '%s' -> http://%s\n", ap, SETUP_AP_PASSWORD,
                WiFi.softAPIP().toString().c_str());
}

bool wifiConnect(uint32_t timeoutMs) {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < timeoutMs) delay(250);
  if (WiFi.status() == WL_CONNECTED) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");   // UTC, required for latency
    Serial.printf("Wi-Fi OK, IP %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  return false;
}

// ---------------------------------------------------------------- setup
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  bootId = esp_random() & 0xFFFFFF;
  delay(200);

  // settings reset: BOOT held for 3 s after power-on
  uint32_t t0 = millis();
  while (digitalRead(PIN_BOOT) == LOW && millis() - t0 < 3000) delay(10);
  if (millis() - t0 >= 3000) { clearSettings(); Serial.println("Settings cleared."); }

  loadSettings();
  Serial.printf("\nWoolWash-IoT FW %s, machine %s\n", FW_VERSION, cfg.mid.c_str());

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

  if (cfg.ssid.isEmpty() || !wifiConnect(30000)) {
    if (!cfg.ssid.isEmpty()) Serial.println("Wi-Fi failed -> setup portal (5 min), then retry.");
    startPortal();
    return;
  }
  web.on("/", pageStatus);
  web.on("/json", []() { web.send(200, "application/json", lastBody); });
  web.begin();
  if (cfg.mqttHost.length()) {
    mqtt.setServer(cfg.mqttHost.c_str(), cfg.mqttPort);
    mqtt.setBufferSize(1024);
  }
  ds.requestTemperatures();
}

// ---------------------------------------------------------------- loop
void loop() {
  web.handleClient();
  if (portalMode) {
    dns.processNextRequest();
    digitalWrite(PIN_LED, (millis() / 250) % 2);
    // if a Wi-Fi was configured but unreachable, retry every 5 minutes
    if (!cfg.ssid.isEmpty() && millis() > 300000UL) ESP.restart();
    return;
  }
  bool useMqtt = cfg.mqttHost.length() > 0;
  if (useMqtt) {
    if (!mqtt.connected()) mqtt.connect(cfg.mid.c_str());
    mqtt.loop();
  }
  uint32_t now = millis();
  if (now - lastSend < PERIOD_MS) return;
  float dt = (now - lastSend) / 1000.0f;
  lastSend = now;
  if (WiFi.status() != WL_CONNECTED) wifiConnect(5000);

  JsonDocument doc;
  doc["machine_id"] = cfg.mid;
  doc["source"] = "device";
  doc["fw"] = FW_VERSION;
  time_t ts; time(&ts); doc["ts"] = (double)ts;   // server substitutes its time if NTP not synced
  struct timeval tv; gettimeofday(&tv, nullptr);
  doc["seq"] = txSeq++;
  doc["boot_id"] = bootId;
  if (tv.tv_sec > 1600000000) doc["tx_ms"] = (double)tv.tv_sec * 1000.0 + tv.tv_usec / 1000;
  doc["rssi"] = WiFi.RSSI();

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
  feed = scale.get_units(5);   // replace with belt-scale throughput for your conveyor
#endif
  feedTotalKg += feed * dt / 3600.0;
  doc["feed_kg_h"] = feed;
  doc["feed_total_kg"] = round(feedTotalKg * 100) / 100.0;

  String body;
  serializeJson(doc, body);
  lastBody = body;
  bool ok = false;
  if (useMqtt) {
    String topic = "woolwash/" + cfg.mid + "/telemetry";
    ok = mqtt.publish(topic.c_str(), body.c_str());
    lastHttpCode = ok ? 200 : -1;
  } else if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.setTimeout(4000);
    http.begin(net, cfg.url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Token", cfg.token);
    lastHttpCode = http.POST(body);
    ok = lastHttpCode == 200;
    http.end();
  }
  digitalWrite(PIN_LED, ok ? HIGH : LOW);
  Serial.printf("seq %lu  send %s (%d)  %u bytes\n", (unsigned long)(txSeq - 1), ok ? "OK" : "FAIL",
                lastHttpCode, body.length());
}
