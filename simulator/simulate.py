"""
WoolWash-IoT machine simulator (digital twin for testing).

Emits the SAME JSON payload as the ESP32 firmware, tagged "source": "sim",
so simulated rows can always be separated from real measurements.

    python simulate.py                       # 1 machine, real time, HTTP to localhost
    python simulate.py --speed 30 --lab-every 20 --fault heater:3@600
    python simulate.py --mqtt localhost      # publish to MQTT instead of HTTP

!! Simulated data is for software testing only. It must NOT be reported as
!! experimental results in a dissertation or journal paper.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
from softsensor import prior  # noqa: E402

SETPOINT = [60.0, 60.0, 55.0, 50.0, 45.0]   # degC, scour bowls 1-2, rinse 3-5
LEVEL_NOM = 60.0                            # cm
TURB_REFRESH = 850.0                        # NTU -> partial liquor change


class Machine:
    def __init__(self, mid: str, geom: dict, seed: int = 1):
        self.id = mid
        self.geom = geom
        self.rng = random.Random(seed)
        self.t = 0.0
        self.temp = [20.0] * 5
        self.level = [LEVEL_NOM] * 5
        self.turb = [50.0] * 5
        self.energy_kwh = 0.0
        self.water_l = 0.0
        self.feed_kg = 0.0
        self.faults: list[tuple[str, int, float]] = []
        self.refresh_flow = 0.0

    # "true" residual moisture (unknown to the soft sensor except via lab samples)
    def true_moisture(self, omega, feed, temp, turb):
        g = self.geom
        return (prior(g["d_hole"], g["d_drum"], g["gap"])
                + 0.40 * (omega - 16.0) + 0.02 * (feed - 425.0)
                - 0.08 * (temp - 55.0) + 0.002 * (turb - 400.0)
                + self.rng.gauss(0, 0.35))

    def active(self, kind, idx=None):
        return any(k == kind and (idx is None or i == idx) and self.t >= at for k, i, at in self.faults)

    def step(self, dt: float) -> dict:
        r = self.rng
        self.t += dt
        hrs = dt / 3600
        # throughput with slow shift-scale variation
        feed = 425 + 20 * math.sin(self.t / 1800) + r.gauss(0, 5)
        self.feed_kg += feed * hrs
        # squeeze drum: omega = 16 rad/s, slip fault reduces speed
        omega = 16.0 + r.gauss(0, 0.15)
        if self.active("drum"):
            omega -= 4.0 + r.gauss(0, 0.5)
        self.refresh_flow = 0.0
        bowls = []
        for i in range(5):
            heater_ok = not self.active("heater", i + 1)
            target = SETPOINT[i] if heater_ok else 20.0
            tau = 600.0
            self.temp[i] += (target - self.temp[i]) * (1 - math.exp(-dt / tau)) + r.gauss(0, 0.05)
            # dirt load is highest in bowl 1, decays downstream (~16-18 %/bowl removal)
            dirt_in = feed * 0.9 * (0.83 ** i)
            self.turb[i] += dirt_in * dt / 3600 * 2.0
            self.level[i] -= 0.4 * hrs * 60 * (feed / 425)  # carry-out with wool
            if self.active("leak", i + 1):
                self.level[i] -= 6.0 * hrs * 60
            refill = 0.0
            if self.level[i] < LEVEL_NOM - 2:
                refill = 25.0  # L/min make-up valve
                self.level[i] += refill * dt / 60 / 25.0
            if self.turb[i] > TURB_REFRESH:
                self.turb[i] *= 0.55
                refill += 250.0 * 60 / max(dt, 1)  # 250 L partial change (as L/min over dt)
            self.refresh_flow += refill
            bowls.append({
                "id": i + 1,
                "temp_c": round(self.temp[i], 2),
                "level_cm": round(self.level[i] + r.gauss(0, 0.3), 1),
                "turbidity_ntu": round(self.turb[i] + r.gauss(0, 8), 1),
            })
        water_lpm = self.refresh_flow
        self.water_l += water_lpm * dt / 60
        power = 4200 * (0.85 + 0.15 * feed / 425) + r.gauss(0, 40)
        if self.active("drum"):
            power += 600
        self.energy_kwh += power / 1000 * hrs
        true_w = self.true_moisture(omega, feed, self.temp[-1], max(self.turb))
        return {
            "machine_id": self.id, "ts": time.time(), "source": "sim",
            "bowls": bowls,
            "squeeze": [{"stage": 1, "drum_omega": round(omega, 3), "gap_mm": self.geom["gap"]}],
            "rake_speed_mps": round(0.15 + r.gauss(0, 0.003), 4),
            "feed_kg_h": round(feed, 1), "feed_total_kg": round(self.feed_kg, 2),
            "power_w": round(power, 1), "energy_kwh": round(self.energy_kwh, 4),
            "water_lpm": round(water_lpm, 2), "water_total_l": round(self.water_l, 1),
            "_true_moisture": round(true_w, 2),
        }


def http_post(url, body, token):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Token": token})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default="changeme")
    ap.add_argument("--machine", default="WW-SIM-01")
    ap.add_argument("--interval", type=float, default=2.0, help="real seconds between messages")
    ap.add_argument("--speed", type=float, default=1.0, help="simulated seconds per real second")
    ap.add_argument("--lab-every", type=float, default=0, help="simulated minutes between lab samples")
    ap.add_argument("--fault", action="append", default=[],
                    help="kind[:bowl]@sim_seconds, kind in heater|leak|drum, e.g. heater:3@600")
    ap.add_argument("--geom", default="2,250,3", help="d_hole,d_drum,gap in mm")
    ap.add_argument("--mqtt", default=None, help="MQTT broker host (instead of HTTP)")
    ap.add_argument("--steps", type=int, default=0, help="stop after N messages (0 = forever)")
    a = ap.parse_args()

    d, D, g = (float(x) for x in a.geom.split(","))
    m = Machine(a.machine, {"d_hole": d, "d_drum": D, "gap": g})
    for f in a.fault:
        kind, at = f.split("@")
        k, _, idx = kind.partition(":")
        m.faults.append((k, int(idx) if idx else 0, float(at)))

    mq = None
    if a.mqtt:
        import paho.mqtt.client as mqtt
        mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mq.connect(a.mqtt, 1883)
        mq.loop_start()

    next_lab = a.lab_every * 60 if a.lab_every else None
    n = 0
    print(f"simulating {a.machine} -> {'mqtt://' + a.mqtt if mq else a.server}  (Ctrl+C to stop)")
    while True:
        p = m.step(a.interval * a.speed)
        true_w = p.pop("_true_moisture")
        try:
            if mq:
                mq.publish(f"woolwash/{a.machine}/telemetry", json.dumps(p))
                pred = "?"
            else:
                pred = http_post(a.server + "/api/telemetry", p, a.token)["moisture_pred"]
            if next_lab is not None and m.t >= next_lab:
                next_lab += a.lab_every * 60
                http_post(a.server + "/api/lab", {"machine": a.machine, "moisture_pct": round(true_w, 2),
                                                  "note": "SIMULATED lab sample"}, a.token)
                print(f"  lab sample W={true_w:.2f}%")
            if n % 10 == 0:
                print(f"t={m.t/60:7.1f} min  T1={p['bowls'][0]['temp_c']:5.1f}  "
                      f"omega={p['squeeze'][0]['drum_omega']:5.2f}  W_true={true_w:5.2f}  W_pred={pred}")
        except Exception as e:  # noqa: BLE001
            print("send failed:", e)
        n += 1
        if a.steps and n >= a.steps:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
