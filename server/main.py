"""
WoolWash-IoT server: telemetry ingest (HTTP + optional MQTT), SQLite storage,
soft sensor, alerts, KPIs, CSV export, WebSocket live feed, web/mobile app.

Run:  python -m uvicorn main:app --host 0.0.0.0 --port 8000   (from this folder)
Env:  WW_TOKEN     device token (default: changeme)
      WW_MQTT_HOST optional MQTT broker host -> subscribes to woolwash/+/telemetry
      WW_DB        sqlite path (default: woolwash.db)
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from softsensor import SoftSensor

BASE = Path(__file__).resolve().parent
WEB = BASE.parent / "app"
DB_PATH = os.environ.get("WW_DB", str(BASE / "woolwash.db"))
TOKEN = os.environ.get("WW_TOKEN", "changeme")

# Default geometry = rational values from the dissertation; editable per machine.
DEFAULT_GEOM = {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0, "rake_len": 250.0}

# Alert limits (editable in /api/config). Temperatures are typical for wool scouring.
LIMITS = {
    "temp_min": [55, 55, 50, 45, 40],
    "temp_max": [65, 65, 60, 55, 50],
    "level_min_cm": 40.0,
    "turbidity_max_ntu": 800.0,     # dirty-liquor advisory switches ON above this ...
    "turbidity_off_ntu": 700.0,     # ... and OFF only below this (hysteresis)
    "turbidity_debounce_n": 15,     # ON only after this many consecutive messages above (15 x 2 s = 30 s)
    "omega_nom": 16.0,
    "omega_tol": 2.0,
    "moisture_max": 60.0,
}

# ----------------------------------------------------------------- storage
_lock = threading.Lock()
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.executescript(
    """
CREATE TABLE IF NOT EXISTS telemetry(
  id INTEGER PRIMARY KEY, machine TEXT, ts REAL, source TEXT, payload TEXT,
  moisture_pred REAL, energy_kwh REAL, water_l REAL, feed_kg REAL);
CREATE INDEX IF NOT EXISTS ix_tel ON telemetry(machine, ts);
CREATE TABLE IF NOT EXISTS lab(
  id INTEGER PRIMARY KEY, machine TEXT, ts REAL, moisture_pct REAL, note TEXT, op TEXT, geom TEXT);
CREATE TABLE IF NOT EXISTS machines(id TEXT PRIMARY KEY, geom TEXT);
CREATE TABLE IF NOT EXISTS machine_limits(id TEXT PRIMARY KEY, limits TEXT);
"""
)
# columns added for the factory-validation template (packet log, out-of-sample calibration)
for _sql in ("ALTER TABLE telemetry ADD COLUMN rx_ms REAL",
             "ALTER TABLE lab ADD COLUMN pred_before REAL"):
    try:
        db.execute(_sql)
    except sqlite3.OperationalError:
        pass  # column already exists


def q(sql, args=(), one=False):
    with _lock:
        cur = db.execute(sql, args)
        rows = cur.fetchall()
        db.commit()
    return (rows[0] if rows else None) if one else rows


def geom_of(machine: str) -> dict:
    r = q("SELECT geom FROM machines WHERE id=?", (machine,), one=True)
    if r:
        return json.loads(r[0])
    q("INSERT OR IGNORE INTO machines VALUES(?,?)", (machine, json.dumps(DEFAULT_GEOM)))
    return dict(DEFAULT_GEOM)


sensors: dict[str, SoftSensor] = {}


def sensor_of(machine: str) -> SoftSensor:
    if machine not in sensors:
        s = SoftSensor()
        rows = q("SELECT moisture_pct, op, geom FROM lab WHERE machine=?", (machine,))
        s.fit([{**json.loads(g), **json.loads(o), "moisture_pct": m} for m, o, g in rows])
        sensors[machine] = s
    return sensors[machine]


# ----------------------------------------------------------------- logic
def op_features(p: dict) -> dict:
    bowls = p.get("bowls", [])
    last = bowls[-1] if bowls else {}
    sq = (p.get("squeeze") or [{}])[0]
    return {
        "drum_omega": sq.get("drum_omega", 16.0),
        "feed_kg_h": p.get("feed_kg_h", 425.0),
        "temp_c": last.get("temp_c", 55.0),
        "turbidity_ntu": max((b.get("turbidity_ntu", 0) for b in bowls), default=400.0),
    }


_limit_cache: dict[str, dict] = {}


def limits_of(machine: str | None) -> dict:
    """Default LIMITS overridden by the per-machine values set at commissioning (PUT /api/limits/{id})."""
    if not machine:
        return LIMITS
    if machine not in _limit_cache:
        r = q("SELECT limits FROM machine_limits WHERE id=?", (machine,), one=True)
        _limit_cache[machine] = {**LIMITS, **(json.loads(r[0]) if r else {})}
    return _limit_cache[machine]


# dirty-liquor advisory state per (machine, bowl): debounce counter + latched flag
_adv: dict[tuple, dict] = {}


def _liquor_dirty(machine, bowl, tb, L, update):
    if machine is None:                                  # stateless use (e.g. tests, one-off checks)
        return tb > L["turbidity_max_ntu"]
    st = _adv.setdefault((machine, bowl), {"active": False, "count": 0})
    if update:
        if not st["active"]:
            st["count"] = st["count"] + 1 if tb > L["turbidity_max_ntu"] else 0
            if st["count"] >= int(L["turbidity_debounce_n"]):
                st["active"] = True
        elif tb < L["turbidity_off_ntu"]:
            st["active"], st["count"] = False, 0
    return st["active"]


def alerts_for(p: dict, moisture: float, machine: str | None = None, update: bool = True) -> list[dict]:
    L = limits_of(machine)
    out = []
    for i, b in enumerate(p.get("bowls", [])):
        n = b.get("id", i + 1)
        t = b.get("temp_c")
        if t is not None and i < 5:
            if t < L["temp_min"][i]:
                out.append({"level": "warn", "code": "temp_low", "bowl": n, "value": t})
            elif t > L["temp_max"][i]:
                out.append({"level": "crit", "code": "temp_high", "bowl": n, "value": t})
        lv = b.get("level_cm")
        if lv is not None and lv < L["level_min_cm"]:
            out.append({"level": "crit", "code": "level_low", "bowl": n, "value": lv})
        tb = b.get("turbidity_ntu")
        if tb is not None and _liquor_dirty(machine, n, tb, L, update):
            out.append({"level": "warn", "code": "liquor_dirty", "bowl": n, "value": tb})
    for s in p.get("squeeze", []):
        w = s.get("drum_omega")
        if w is not None and abs(w - L["omega_nom"]) > L["omega_tol"]:
            out.append({"level": "warn", "code": "omega_dev", "stage": s.get("stage"), "value": w})
    if moisture > L["moisture_max"]:
        out.append({"level": "warn", "code": "moisture_high", "value": round(moisture, 2)})
    return out


clients: set[WebSocket] = set()
loop_ref: dict = {}


def ingest(p: dict) -> dict:
    rx_ms = time.time() * 1000.0  # server receive time (UTC epoch ms) for latency analysis
    machine = str(p.get("machine_id", "WW-01"))
    ts = float(p.get("ts") or time.time())
    if ts < 1e9:  # device without RTC/NTP sent uptime seconds
        ts = time.time()
    geom = geom_of(machine)
    m = sensor_of(machine).predict(geom, op_features(p))
    al = alerts_for(p, m, machine)
    q(
        "INSERT INTO telemetry(machine,ts,source,payload,moisture_pred,energy_kwh,water_l,feed_kg,rx_ms)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (machine, ts, p.get("source", "device"), json.dumps(p), m,
         p.get("energy_kwh"), p.get("water_total_l"), p.get("feed_total_kg"), rx_ms),
    )
    msg = {"type": "telemetry", "machine": machine, "ts": ts, "data": p,
           "moisture_pred": round(m, 2), "alerts": al}
    lp = loop_ref.get("loop")
    if lp and clients:
        asyncio.run_coroutine_threadsafe(broadcast(msg), lp)
    return msg


async def broadcast(msg):
    dead = []
    for c in list(clients):
        try:
            await c.send_json(msg)
        except Exception:
            dead.append(c)
    for c in dead:
        clients.discard(c)


def kpis(machine: str, since: float) -> dict:
    rows = q("SELECT ts,energy_kwh,water_l,feed_kg,moisture_pred FROM telemetry "
             "WHERE machine=? AND ts>=? ORDER BY ts", (machine, since))
    if len(rows) < 2:
        return {}
    a, b = rows[0], rows[-1]
    de = (b[1] or 0) - (a[1] or 0)
    dw = (b[2] or 0) - (a[2] or 0)
    df = (b[3] or 0) - (a[3] or 0)
    mo = [r[4] for r in rows if r[4] is not None]
    return {
        "hours": round((b[0] - a[0]) / 3600, 3),
        "energy_kwh": round(de, 3), "water_l": round(dw, 1), "feed_kg": round(df, 1),
        "kwh_per_kg": round(de / df, 4) if df > 0 else None,
        "l_per_kg": round(dw / df, 3) if df > 0 else None,
        "moisture_mean": round(sum(mo) / len(mo), 2) if mo else None,
    }


# ----------------------------------------------------------------- MQTT (optional)
def start_mqtt():
    host = os.environ.get("WW_MQTT_HOST")
    if not host:
        return
    import paho.mqtt.client as mqtt

    def on_msg(_c, _u, msg):
        try:
            ingest(json.loads(msg.payload))
        except Exception as e:  # noqa: BLE001
            print("mqtt payload error:", e)

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_message = on_msg
    c.on_connect = lambda cl, *_: cl.subscribe("woolwash/+/telemetry")
    c.connect(host, int(os.environ.get("WW_MQTT_PORT", 1883)))
    c.loop_start()
    print("MQTT subscribed at", host)


# ----------------------------------------------------------------- API
app = FastAPI(title="WoolWash-IoT")


@app.on_event("startup")
async def _startup():
    loop_ref["loop"] = asyncio.get_running_loop()
    start_mqtt()


@app.post("/api/telemetry")
def post_telemetry(payload: dict, x_token: str = Header(default="")):
    if x_token != TOKEN:
        raise HTTPException(401, "bad token")
    msg = ingest(payload)
    return {"ok": True, "moisture_pred": msg["moisture_pred"], "alerts": msg["alerts"]}


@app.get("/api/machines")
def machines():
    rows = q("SELECT machine, MAX(ts), COUNT(*) FROM telemetry GROUP BY machine")
    return [{"id": r[0], "last_ts": r[1], "count": r[2]} for r in rows]


@app.get("/api/latest/{machine}")
def latest(machine: str):
    r = q("SELECT ts,payload,moisture_pred FROM telemetry WHERE machine=? ORDER BY ts DESC LIMIT 1",
          (machine,), one=True)
    if not r:
        raise HTTPException(404, "no data")
    p = json.loads(r[1])
    return {"ts": r[0], "data": p, "moisture_pred": round(r[2], 2),
            "alerts": alerts_for(p, r[2], machine, update=False)}


@app.get("/api/history/{machine}")
def history(machine: str, minutes: float = 60, max_points: int = 600):
    since = time.time() - minutes * 60
    rows = q("SELECT ts,payload,moisture_pred FROM telemetry WHERE machine=? AND ts>=? ORDER BY ts",
             (machine, since))
    step = max(1, len(rows) // max_points)
    out = []
    for ts, pl, m in rows[::step]:
        p = json.loads(pl)
        out.append({
            "ts": ts, "moisture": m, "power_w": p.get("power_w"),
            "temps": [b.get("temp_c") for b in p.get("bowls", [])],
            "turb": [b.get("turbidity_ntu") for b in p.get("bowls", [])],
            "omega": (p.get("squeeze") or [{}])[0].get("drum_omega"),
        })
    return {"points": out, "kpi": kpis(machine, since)}


class LabSample(BaseModel):
    machine: str = "WW-01"
    moisture_pct: float
    note: str = ""


@app.post("/api/lab")
def add_lab(s: LabSample):
    """Operator enters oven-dry residual moisture of a sample taken after squeezing.
    The current operating features are attached automatically and the soft sensor is refit."""
    r = q("SELECT payload FROM telemetry WHERE machine=? ORDER BY ts DESC LIMIT 1", (s.machine,), one=True)
    op = op_features(json.loads(r[0])) if r else {}
    geom = geom_of(s.machine)
    # prediction made BEFORE this sample is used for training = honest out-of-sample error
    pred_before = sensor_of(s.machine).predict(geom, op)
    q("INSERT INTO lab(machine,ts,moisture_pct,note,op,geom,pred_before) VALUES(?,?,?,?,?,?,?)",
      (s.machine, time.time(), s.moisture_pct, s.note, json.dumps(op), json.dumps(geom), pred_before))
    sensors.pop(s.machine, None)
    return {"ok": True, "model": sensor_of(s.machine).info()}


@app.get("/api/lab/{machine}")
def list_lab(machine: str):
    rows = q("SELECT ts,moisture_pct,note,op FROM lab WHERE machine=? ORDER BY ts DESC", (machine,))
    return [{"ts": a, "moisture_pct": b, "note": c, "op": json.loads(d)} for a, b, c, d in rows]


@app.get("/api/model/{machine}")
def model(machine: str):
    return {"geometry": geom_of(machine), **sensor_of(machine).info()}


@app.put("/api/geometry/{machine}")
def set_geom(machine: str, g: dict, x_token: str = Header(default="")):
    if x_token != TOKEN:
        raise HTTPException(401, "bad token")
    geom = {**geom_of(machine), **{k: float(v) for k, v in g.items() if k in DEFAULT_GEOM}}
    q("INSERT OR REPLACE INTO machines VALUES(?,?)", (machine, json.dumps(geom)))
    return geom


@app.get("/api/config")
def get_config():
    return LIMITS


@app.get("/api/limits/{machine}")
def get_limits(machine: str):
    return limits_of(machine)


@app.put("/api/limits/{machine}")
def set_limits(machine: str, new: dict, x_token: str = Header(default="")):
    """Commissioning: override alarm limits for one machine, e.g. {"turbidity_max_ntu": 850}."""
    if x_token != TOKEN:
        raise HTTPException(401, "bad token")
    unknown = [k for k in new if k not in LIMITS]
    if unknown:
        raise HTTPException(400, f"unknown limit(s): {unknown}")
    r = q("SELECT limits FROM machine_limits WHERE id=?", (machine,), one=True)
    cur = {**(json.loads(r[0]) if r else {}), **new}
    q("INSERT OR REPLACE INTO machine_limits VALUES(?,?)", (machine, json.dumps(cur)))
    _limit_cache.pop(machine, None)
    for key in [k for k in _adv if k[0] == machine]:
        _adv.pop(key)                     # restart the advisory state with the new limits
    return limits_of(machine)


@app.get("/api/export/{machine}.csv")
def export(machine: str, hours: float = 24):
    rows = q("SELECT ts,source,payload,moisture_pred FROM telemetry WHERE machine=? AND ts>=? ORDER BY ts",
             (machine, time.time() - hours * 3600))

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        hdr = ["ts", "source", "power_w", "energy_kwh", "water_lpm", "water_total_l", "feed_kg_h",
               "rake_speed_mps", "drum_omega", "moisture_pred"]
        hdr += [f"b{i}_{k}" for i in range(1, 6) for k in ("temp_c", "level_cm", "turbidity_ntu")]
        w.writerow(hdr)
        for ts, src, pl, m in rows:
            p = json.loads(pl)
            bowls = p.get("bowls", []) + [{}] * 5
            row = [ts, src, p.get("power_w"), p.get("energy_kwh"), p.get("water_lpm"),
                   p.get("water_total_l"), p.get("feed_kg_h"), p.get("rake_speed_mps"),
                   (p.get("squeeze") or [{}])[0].get("drum_omega"), round(m, 3)]
            for b in bowls[:5]:
                row += [b.get("temp_c"), b.get("level_cm"), b.get("turbidity_ntu")]
            w.writerow(row)
        yield buf.getvalue()

    return StreamingResponse(gen(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={machine}.csv"})


def _csv_response(header, rows, name):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={name}"})


@app.get("/api/validation/{machine}/packets.csv")
def packets_csv(machine: str, hours: float = 24, trial: str = ""):
    """Rows for the 'Packet delivery' sheet of IEEE_IoT_Factory_Validation_Template.xlsx.
    One row per transmitted sequence number; gaps in the sequence are reported as lost packets
    (their TX time is unknown to the server and left blank)."""
    rows = q("SELECT payload, rx_ms, source FROM telemetry WHERE machine=? AND ts>=? ORDER BY rx_ms",
             (machine, time.time() - hours * 3600))
    by_boot: dict = {}
    for pl, rx, src in rows:
        p = json.loads(pl)
        if "seq" not in p:
            continue
        by_boot.setdefault(str(p.get("boot_id", "0")), {})[int(p["seq"])] = (p.get("tx_ms"), rx, src)
    out = []
    for boot, seqs in by_boot.items():
        for s in range(min(seqs), max(seqs) + 1):
            tid = trial or f"{machine}-{boot}"
            if s in seqs:
                tx, rx, src = seqs[s]
                note = "SIMULATED" if src == "sim" else ""
                out.append([tid, s, tx if tx else "", round(rx) if rx else "", "", "", "Wi-Fi/HTTP", note])
            else:
                out.append([tid, s, "", "", "", "", "Wi-Fi/HTTP", "lost (sequence gap; TX time not logged)"])
    hdr = ["Trial ID", "TX sequence #", "TX UTC epoch (ms)", "RX UTC epoch (ms)", "Received?",
           "Latency (ms)", "Gateway / link", "Notes / reason lost"]
    return _csv_response(hdr, out, f"{machine}_packets.csv")


@app.get("/api/validation/{machine}/calibration.csv")
def calibration_csv(machine: str, trial: str = ""):
    """Rows for the 'Sensor calibration' sheet: oven-dry lab moisture (reference) vs the soft-sensor
    prediction made BEFORE that sample was used for training (out-of-sample)."""
    rows = q("SELECT ts, moisture_pct, pred_before, note FROM lab WHERE machine=? ORDER BY ts", (machine,))
    out = []
    for ts, ref, pred, note in rows:
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        out.append([trial or machine, "Residual moisture soft sensor (%)", machine, iso, ref,
                    "" if pred is None else round(pred, 3),
                    f"Oven-dry 105 C reference. {note}".strip()])
    hdr = ["Trial ID", "Sensor type", "Sensor ID", "UTC timestamp", "Reference reading", "IoT reading",
           "Reference instrument / notes"]
    return _csv_response(hdr, out, f"{machine}_calibration.csv")


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    clients.add(sock)
    try:
        while True:
            await sock.receive_text()
    except WebSocketDisconnect:
        clients.discard(sock)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="app")
