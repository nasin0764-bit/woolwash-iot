"""
End-to-end emulated deployment ("dress rehearsal") of the complete WoolWash-IoT pipeline.

    python tools/e2e_emulation.py            # ~10 min; writes results/emulation/*.json and field_rehearsal/

What is REAL here and what is EMULATED:
  real      the server process (uvicorn + FastAPI + SQLite), its HTTP API, the soft sensor with staged online
            calibration, the alarm rules, the KPI accounting, the validation exports and tools/analyze_field.py
  emulated  the machines (simulator/simulate.py plant model + a hidden per-plant moisture offset), the firmware
            layer (seq / boot_id / counters that restart at boot, one message per 2 s), the Wi-Fi channel
            (Gilbert-Elliott burst loss, an access-point outage), a node reboot, a drum retrofit, supervised
            faults and the operator's oven-dry lab samples (truth + N(0, 0.664 pp))
Time is compressed: 8 simulated hours per node are sent as fast as the server accepts them, from three nodes
in parallel. Every row is tagged source=sim / SIMULATED. NOTHING produced here is factory data.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "results" / "emulation"
OUT.mkdir(parents=True, exist_ok=True)

from simulate import Machine  # noqa: E402
from softsensor import prior, FEATURES  # noqa: E402

SEED = 2026
DT = 2.0                       # firmware message period (s)
WARMUP_S = 3600.0              # heating-up, not transmitted
CAMPAIGN_S = float(os.environ.get("WW_E2E_HOURS", "8")) * 3600.0   # one shift per node
LAB_EVERY_S = 20 * 60.0        # operator takes one oven-dry sample every 20 min
LAB_SD = float(np.sqrt(0.441))  # pooled replicate SD of the dissertation's Table 3.9 (pp)
TOKEN = "emul"
# Gilbert-Elliott channel: loss 0.5 % in the good state, 50 % in the bad state, mean burst 10 packets (20 s)
GE = {"p_gb": 0.002, "p_bg": 0.10, "loss_g": 0.005, "loss_b": 0.50}
H = 3600.0
NODES = [
    {"id": "WW-E1", "geom": {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0}, "offset": 1.5,
     "reboot_at": 4.0 * H, "reboot_link_loss_s": 60.0, "reboot_down_s": 20.0,
     "faults": [("leak", 2, 6.5 * H, 10 * 60)]},
    {"id": "WW-E2", "geom": {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0}, "offset": -1.0,
     "outage": (5.0 * H, 10 * 60.0),
     "faults": [("heater", 3, 6.0 * H, 20 * 60)]},
    {"id": "WW-E3", "geom": {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0}, "offset": 0.5,
     "retrofit": (4.0 * H, {"d_hole": 2.0, "d_drum": 300.0, "gap": 3.0}),
     "faults": [("drum", 0, 7.0 * H, 5 * 60)]},
]
FAULT_CODE = {"heater": "temp_low", "leak": "level_low", "drum": "omega_dev"}
FAULT_RECOVERY_S = 60 * 60      # after a fault is cleared, alarms within this window are not counted as false
ADVISORY = {"liquor_dirty", "moisture_high"}


class Plant(Machine):
    """simulate.Machine with a hidden plant-specific moisture offset (unknown to the DoE prior)."""

    def __init__(self, mid, geom, seed, offset):
        super().__init__(mid, geom, seed=seed)
        self.offset = offset

    def true_moisture(self, omega, feed, temp, turb):
        return super().true_moisture(omega, feed, temp, turb) + self.offset


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def post(url, body, timeout=10):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def put(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
                                 headers={"Content-Type": "application/json", "X-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(url, raw=False):
    with urllib.request.urlopen(url, timeout=60) as r:
        b = r.read()
    return b.decode("utf-8") if raw else json.loads(b)


# ----------------------------------------------------------------- one emulated node (firmware + channel)
def run_node(cfg, base, t_epoch0, idx, log):
    rng = random.Random(SEED + idx)
    plant = Plant(cfg["id"], dict(cfg["geom"]), seed=SEED + 10 * idx, offset=cfg["offset"])
    while plant.t < WARMUP_S:
        plant.step(DT)
    t_start = plant.t
    totals0 = (plant.energy_kwh, plant.water_l, plant.feed_kg)

    def boot():
        return {"boot_id": rng.randrange(1 << 24), "seq": 0,
                "c0": (plant.energy_kwh, plant.water_l, plant.feed_kg)}

    fw = boot()
    ge_bad = False
    st = {"sent": 0, "delivered": 0, "lost_channel": 0, "lost_outage": 0, "lost_reboot_link": 0,
          "boots": 1, "not_sent_down": 0, "per_boot": {}}
    lab, faults, alerts_seen = [], [], []
    next_lab = t_start + LAB_EVERY_S
    reboot_done = retrofit_done = False
    pending = [dict(kind=k, idx=i, onset=t_start + on, clear=t_start + on + dur, detected=None)
               for k, i, on, dur in cfg.get("faults", [])]
    rx_lat = []
    while plant.t < t_start + CAMPAIGN_S:
        rel = plant.t - t_start
        # ---- scheduled events
        for f in pending:
            if f["onset"] <= plant.t + DT and (f["kind"], f["idx"], f["onset"]) not in plant.faults \
                    and plant.t < f["clear"]:
                plant.faults.append((f["kind"], f["idx"], f["onset"]))
            if plant.t >= f["clear"]:
                plant.faults = [x for x in plant.faults if x != (f["kind"], f["idx"], f["onset"])]
        if "retrofit" in cfg and not retrofit_done and rel >= cfg["retrofit"][0]:
            plant.geom = dict(cfg["retrofit"][1])
            put(f"{base}/api/geometry/{cfg['id']}", plant.geom)
            retrofit_done = True
        if "reboot_at" in cfg and not reboot_done and rel >= cfg["reboot_at"]:
            for _ in range(int(cfg["reboot_down_s"] / DT)):     # node off: nothing is transmitted
                plant.step(DT)
                st["not_sent_down"] += 1
            fw = boot()
            st["boots"] += 1
            reboot_done = True
        rel_tx = plant.t - t_start                     # schedule time of this transmission slot
        p = plant.step(DT)
        true_w = p.pop("_true_moisture")
        rel = plant.t - t_start
        # ---- firmware layer: counters relative to this boot, seq increments on every attempt
        p["energy_kwh"] = round(plant.energy_kwh - fw["c0"][0], 4)
        p["water_total_l"] = round(plant.water_l - fw["c0"][1], 1)
        p["feed_total_kg"] = round(plant.feed_kg - fw["c0"][2], 2)
        p.update({"seq": fw["seq"], "boot_id": fw["boot_id"], "ts": t_epoch0 + rel, "fw": "1.1.0",
                  "rssi": -62, "tx_ms": round(time.time() * 1000)})
        fw["seq"] += 1
        st["sent"] += 1
        pb = st["per_boot"].setdefault(str(fw["boot_id"]), {"sent": 0, "delivered": 0, "last_delivered_seq": -1})
        pb["sent"] += 1
        # ---- channel
        ge_bad = (rng.random() < GE["p_gb"]) if not ge_bad else (rng.random() >= GE["p_bg"])
        reason = None
        if "outage" in cfg and cfg["outage"][0] <= rel_tx < cfg["outage"][0] + cfg["outage"][1]:
            reason = "lost_outage"
        elif "reboot_at" in cfg and not reboot_done and \
                cfg["reboot_at"] - cfg["reboot_link_loss_s"] <= rel_tx < cfg["reboot_at"]:
            reason = "lost_reboot_link"               # supply dip before the brown-out reset
        elif rng.random() < (GE["loss_b"] if ge_bad else GE["loss_g"]):
            reason = "lost_channel"
        if reason is None:
            try:
                r = post(f"{base}/api/telemetry", p)
                st["delivered"] += 1
                pb["delivered"] += 1
                pb["last_delivered_seq"] = p["seq"]
                cnt = (p["energy_kwh"], p["water_total_l"], p["feed_total_kg"])
                st.setdefault("first_counters", cnt)
                st["last_counters"] = cnt
                codes = {a["code"] for a in r["alerts"]}
                alerts_seen.append((rel, sorted(codes)))
                for f in pending:
                    if f["detected"] is None and plant.t >= f["onset"] and FAULT_CODE[f["kind"]] in codes:
                        f["detected"] = plant.t - f["onset"]
            except Exception:                           # noqa: BLE001  server busy -> lost, like the firmware
                reason = "lost_channel"
        if reason:
            st[reason] += 1
        # ---- operator lab sample (separate path: the app on the plant LAN)
        if plant.t >= next_lab:
            next_lab += LAB_EVERY_S
            ref = true_w + rng.gauss(0, LAB_SD)
            post(f"{base}/api/lab", {"machine": cfg["id"], "moisture_pct": round(ref, 2),
                                     "note": "SIMULATED lab sample (e2e emulation)"})
            lab.append({"rel_h": rel / H, "true": true_w, "ref": round(ref, 2), "geom": dict(plant.geom)})
    totals1 = (plant.energy_kwh, plant.water_l, plant.feed_kg)
    log[cfg["id"]] = {"stats": st, "lab": lab, "faults": pending, "alerts": alerts_seen,
                      "truth_totals": {"energy_kwh": totals1[0] - totals0[0], "water_l": totals1[1] - totals0[1],
                                       "feed_kg": totals1[2] - totals0[2]}}


# ----------------------------------------------------------------- analyses
def rmse(e):
    return float(np.sqrt(np.mean(np.square(e)))) if len(e) else float("nan")


def prequential(node_log, lab_api, calib_rows):
    """Online (prequential) error: each sample is predicted BEFORE it is used for training."""
    lab_api = sorted(lab_api, key=lambda s: s["ts"])
    assert len(lab_api) == len(node_log["lab"]) == len(calib_rows)
    out = []
    for k, (emu, api, cal) in enumerate(zip(node_log["lab"], lab_api, calib_rows)):
        g = emu["geom"]
        p_h = float(cal["IoT reading"])
        p_doe = prior(g["d_hole"], g["d_drum"], g["gap"])
        # data-only ridge on operating features, trained on the previous samples (no geometry information)
        prev = lab_api[:k]
        if k < 3:
            p_r = statistics.fmean([s["moisture_pct"] for s in prev]) if prev else float("nan")
        else:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler
            X = np.array([[s["op"][f] for f in FEATURES] for s in prev])
            sc = StandardScaler().fit(X)
            m = Ridge(alpha=1.0).fit(sc.transform(X), [s["moisture_pct"] for s in prev])
            p_r = float(m.predict(sc.transform([[api["op"][f] for f in FEATURES]]))[0])
        out.append({"k": k, "rel_h": emu["rel_h"], "ref": emu["ref"], "true": emu["true"],
                    "hybrid": p_h, "doe": p_doe, "ridge": p_r, "drum": g["d_drum"]})
    return out


def stage_table(pq_all):
    def sel(cond):
        return [r for rs in pq_all.values() for r in rs if cond(r)]
    groups = {"n=0": sel(lambda r: r["k"] == 0), "1<=n<5": sel(lambda r: 1 <= r["k"] < 5),
              "5<=n<24": sel(lambda r: r["k"] >= 5 and not (r["drum"] == 300.0)),
              "after retrofit": sel(lambda r: r["drum"] == 300.0)}
    res = {}
    for g, rs in groups.items():
        d = {"samples": len(rs)}
        for m in ("hybrid", "doe", "ridge"):
            v = [(r[m] - r["true"]) for r in rs if not math.isnan(r[m])]
            d[m + "_rmse_vs_true"] = rmse(v) if v else None
            v2 = [(r[m] - r["ref"]) for r in rs if not math.isnan(r[m])]
            d[m + "_rmse_vs_lab"] = rmse(v2) if v2 else None
        res[g] = d
    return res


def main():
    tmp = Path(tempfile.mkdtemp(prefix="ww_e2e_"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, WW_DB=str(tmp / "e2e.db"), WW_TOKEN=TOKEN)
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port),
                            "--log-level", "warning"], cwd=str(ROOT / "server"), env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log: dict = {}
    try:
        for _ in range(200):
            try:
                get(f"{base}/api/config")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
        t_epoch0 = time.time() - CAMPAIGN_S - 600          # emulated shift ends just before "now"
        wall0 = time.perf_counter()
        th = [threading.Thread(target=run_node, args=(c, base, t_epoch0, i, log)) for i, c in enumerate(NODES)]
        for t in th:
            t.start()
        for t in th:
            t.join()
        wall = time.perf_counter() - wall0
        print(f"emulation finished in {wall:.0f} s")

        import analyze_field as af
        res = {"what": "END-TO-END EMULATION - simulated plants, firmware layer and channel; real server software. "
                       "NOT factory data.",
               "config": {"nodes": len(NODES), "period_s": DT, "hours_per_node": CAMPAIGN_S / H,
                          "lab_every_min": LAB_EVERY_S / 60, "lab_sd_pp": LAB_SD, "ge_channel": GE,
                          "node_events": {c["id"]: {k: v for k, v in c.items() if k not in ("id", "geom")}
                                          for c in NODES}},
               "wall_s": round(wall, 1)}
        delivered_total = sum(log[c["id"]]["stats"]["delivered"] for c in NODES)
        res["server_load"] = {"messages_delivered": delivered_total,
                              "sustained_msgs_per_s_3_clients": round(delivered_total / wall, 1),
                              "required_msgs_per_s_3_nodes": round(len(NODES) / DT, 2)}
        net, kpi, faults, falsealarm, pq_all = {}, {}, {}, {}, {}
        rehearsal_csvs = []
        for c in NODES:
            mid, L = c["id"], log[c["id"]]
            st = L["stats"]
            pk_txt = get(f"{base}/api/validation/{mid}/packets.csv?hours=48", raw=True)
            pk_path = OUT / f"_{mid}_packets.csv"
            pk_path.write_text(pk_txt, encoding="utf-8")
            rehearsal_csvs.append(str(pk_path))
            pk, _ = af.analyze_packets(None, True, af.csv_packet_rows([pk_path]))
            # losses after the last delivered packet of a boot are invisible to the server
            invisible = sum(b["sent"] - 1 - b["last_delivered_seq"] for b in st["per_boot"].values())
            net[mid] = {"truth": {"sent": st["sent"], "delivered": st["delivered"],
                                  "pdr_pct": 100 * st["delivered"] / st["sent"],
                                  "lost_channel": st["lost_channel"], "lost_outage": st["lost_outage"],
                                  "lost_before_reboot": st["lost_reboot_link"], "boots": st["boots"]},
                        "server_estimate": {"sent": pk["sent"], "received": pk["received"],
                                            "pdr_pct": pk["pdr_pct"],
                                            "latency_ms_median": pk["latency_ms"]["median"],
                                            "latency_ms_p95": pk["latency_ms"]["p95"]},
                        "invisible_tail_losses": invisible}
            # KPI accounting vs plant truth
            hist = get(f"{base}/api/history/{mid}?minutes={(CAMPAIGN_S + 3600) / 60}&max_points=100000")
            k = hist["kpi"]
            T = L["truth_totals"]
            # what a server computing last-minus-first of the cumulative counters would report
            naive = dict(zip(("energy", "water", "feed"),
                             (b - a for a, b in zip(st["first_counters"], st["last_counters"]))))
            kpi[mid] = {
                "truth": {"kwh_per_kg": T["energy_kwh"] / T["feed_kg"], "l_per_kg": T["water_l"] / T["feed_kg"],
                          "feed_kg": T["feed_kg"]},
                "server": {"kwh_per_kg": k["kwh_per_kg"], "l_per_kg": k["l_per_kg"], "feed_kg": k["feed_kg"]},
                "naive_last_minus_first": {"kwh_per_kg": naive["energy"] / naive["feed"] if naive["feed"] else None,
                                           "l_per_kg": naive["water"] / naive["feed"] if naive["feed"] else None,
                                           "feed_kg": naive["feed"]}}
            for kk in ("kwh_per_kg", "l_per_kg", "feed_kg"):
                tv = kpi[mid]["truth"][kk]
                kpi[mid].setdefault("server_error_pct", {})[kk] = 100 * (kpi[mid]["server"][kk] - tv) / tv
                nv = kpi[mid]["naive_last_minus_first"][kk]
                kpi[mid].setdefault("naive_error_pct", {})[kk] = None if nv is None else 100 * (nv - tv) / tv
            # faults and false alarms
            faults[mid] = [{"kind": f["kind"], "bowl": f["idx"], "detected": f["detected"] is not None,
                            "delay_s": f["detected"]} for f in L["faults"]]
            windows = [(f["onset"] - WARMUP_S, f["clear"] - WARMUP_S + FAULT_RECOVERY_S)
                       for f in L["faults"]]
            fa = {}
            for rel, codes in L["alerts"]:
                inside = any(a - 1e-9 <= rel <= b for a, b in windows)
                for cd in codes:
                    if cd in ADVISORY:
                        fa.setdefault("advisory_msgs_" + cd, 0)
                        fa["advisory_msgs_" + cd] += 1
                    elif not inside:
                        fa[cd] = fa.get(cd, 0) + 1
            falsealarm[mid] = fa
            # prequential soft-sensor error
            lab_api = get(f"{base}/api/lab/{mid}")
            cal = list(csv.DictReader(io.StringIO(get(f"{base}/api/validation/{mid}/calibration.csv", raw=True))))
            pq_all[mid] = prequential(L, lab_api, cal)
        res["network"] = net
        res["kpi"] = kpi
        res["faults"] = faults
        res["fault_alarm_messages_outside_fault_windows"] = falsealarm
        res["softsensor_prequential"] = stage_table(pq_all)
        res["softsensor_final_model"] = {c["id"]: get(f"{base}/api/model/{c['id']}") for c in NODES}

        # ---- dress rehearsal of the Section VII tooling on node WW-E1 (watermarked, separate folder)
        reh = OUT / "field_rehearsal"
        reh.mkdir(exist_ok=True)
        wb = reh / "WW-E1_filled_SIMULATED.xlsx"
        r1 = subprocess.run([sys.executable, str(ROOT / "tools" / "fill_template.py"),
                             str(ROOT / "docs" / "IEEE_IoT_Factory_Validation_Template.xlsx"), str(wb),
                             "--server", base, "--machine", "WW-E1", "--hours", "48", "--allow-sim"],
                            capture_output=True, text=True)
        r2 = subprocess.run([sys.executable, str(ROOT / "tools" / "analyze_field.py"), str(wb), "--no-server",
                             "--allow-sim", "--out", str(reh), "--packets-csv", rehearsal_csvs[0]],
                            capture_output=True, text=True)
        res["field_rehearsal"] = {"fill_template_rc": r1.returncode, "fill_template_out": r1.stdout[-600:],
                                  "analyze_field_rc": r2.returncode, "analyze_field_out": r2.stdout[-600:],
                                  "analyze_field_err": r2.stderr[-600:]}
        with open(OUT / "prequential_samples.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["node", "k", "rel_h", "lab_ref", "truth", "hybrid_pred", "doe_pred", "ridge_pred", "drum_mm"])
            for mid, rs in pq_all.items():
                for r in rs:
                    w.writerow([mid, r["k"], round(r["rel_h"], 3), r["ref"], round(r["true"], 3), round(r["hybrid"], 3),
                                round(r["doe"], 3), "" if math.isnan(r["ridge"]) else round(r["ridge"], 3), r["drum"]])
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    (OUT / "e2e_summary.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("server_load", "network", "kpi", "faults", "softsensor_prequential")},
                     indent=1, default=float))
    print("->", OUT)


if __name__ == "__main__":
    main()
