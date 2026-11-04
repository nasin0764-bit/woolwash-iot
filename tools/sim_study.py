"""
Simulation and bench study for the WoolWash-IoT paper (Sec. "Simulation and Bench Study").

    python tools/sim_study.py            # writes results/sim_study/*.json|csv and paper/figs/*.pdf

THREE PARTS, each with a different evidential status:
  S1  Soft-sensor sample efficiency and geometry transfer   -> SIMULATION under stated assumptions
  S2  Server software benchmark                             -> REAL MEASUREMENT of the software on this PC
  S3  Alarm-logic verification with injected faults         -> CODE VERIFICATION on the simulator

Grounded inputs (from the dissertation data, Table 3.9):
  * DoE geometry model b0..b3 (server/softsensor.py)
  * lab-measurement noise SD = pooled replicate SD of Table 3.9 = sqrt(0.441) = 0.664 pp
Assumed inputs (NOT measured; stated in the paper):
  * operating-condition effects on moisture and their ranges (OP_EFFECTS, OP_RANGES)
Nothing produced here is factory IoT data.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "simulator"))
OUT = ROOT / "results" / "sim_study"
FIG = ROOT / "paper" / "figs"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

from softsensor import SoftSensor, prior, NOMINAL  # noqa: E402

SEED = 2026
REPS = 200
N_TEST = 300
LAB_SD = float(np.sqrt(0.441))          # pooled replicate SD, Table 3.9 (pp)
OP_RANGES = {                            # assumed operating variability at the plant
    "drum_omega": ("normal", 16.0, 1.0),
    "feed_kg_h": ("normal", 425.0, 25.0),
    "temp_c": ("normal", 55.0, 3.0),
    "turbidity_ntu": ("uniform", 200.0, 800.0),
}
OP_EFFECTS = {"drum_omega": 0.40, "feed_kg_h": 0.02, "temp_c": -0.08, "turbidity_ntu": 0.002}  # pp per unit, assumed
BASE_GEOM = {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0}
NEW_GEOMS = {"D=300 mm": {"d_hole": 2.0, "d_drum": 300.0, "gap": 3.0},
             "d=3, D=200, h=4 mm": {"d_hole": 3.0, "d_drum": 200.0, "gap": 4.0}}
N_GRID = [0, 1, 2, 3, 5, 10, 20, 40, 60]
FEATS = list(OP_EFFECTS)


# ----------------------------------------------------------------- S1 simulation
def sample_ops(rng, n):
    cols = {}
    for k, (kind, a, b) in OP_RANGES.items():
        cols[k] = rng.normal(a, b, n) if kind == "normal" else rng.uniform(a, b, n)
    return [{k: float(cols[k][i]) for k in cols} for i in range(n)]


def truth(geom, op, scenario, factory_offset):
    w = prior(geom["d_hole"], geom["d_drum"], geom["gap"]) + factory_offset
    for k, beta in OP_EFFECTS.items():
        w += beta * (op[k] - NOMINAL[k])
    if scenario == "nonlinear":
        w += 0.15 * (op["drum_omega"] - 16.0) ** 2 \
             + 0.0004 * (op["feed_kg_h"] - 425.0) * (op["temp_c"] - 55.0) \
             + 0.002 * max(0.0, op["turbidity_ntu"] - 600.0)
    return w


def fit_predict(model, train, test_geom, test_ops):
    """train: list of dicts (geometry + op + moisture_pct). Returns predictions for test."""
    n = len(train)
    if model == "DoE prior only":
        p = prior(test_geom["d_hole"], test_geom["d_drum"], test_geom["gap"])
        return np.full(len(test_ops), p)
    if model.startswith("Hybrid"):
        s = SoftSensor(lam=1.0)
        if model == "Hybrid, unstaged (v1.0)":
            # original rule: prior only below 3 samples, full ridge (unshrunk offset) from 3 samples
            if n < 3:
                return np.full(len(test_ops), prior(test_geom["d_hole"], test_geom["d_drum"], test_geom["gap"]))
            s.N_FULL, s.SHRINK_C = 3, False
        elif model == "Hybrid, staged, no shrinkage":
            s.SHRINK_C = False
        s.fit(train)                       # proposed: prior -> shrunk offset (n<5) -> full ridge
        return np.array([s.predict(test_geom, o) for o in test_ops])
    if n == 0:
        return None                        # purely data-driven models cannot predict
    X = np.array([[t[k] for k in FEATS] for t in train])
    y = np.array([t["moisture_pct"] for t in train])
    Xt = np.array([[o[k] for k in FEATS] for o in test_ops])
    if model == "Ridge (no prior)":
        if n < 3:
            return np.full(len(test_ops), y.mean())
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        sc = StandardScaler().fit(X)
        return Ridge(alpha=1.0).fit(sc.transform(X), y).predict(sc.transform(Xt))
    if model == "Random forest (no prior)":
        if n < 3:
            return np.full(len(test_ops), y.mean())
        from sklearn.ensemble import RandomForestRegressor
        rf = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=0)
        return rf.fit(X, y).predict(Xt)
    raise ValueError(model)


MODELS = ["DoE prior only", "Hybrid (proposed)", "Hybrid, unstaged (v1.0)", "Hybrid, staged, no shrinkage",
          "Ridge (no prior)", "Random forest (no prior)"]
PLOT_MODELS = ["DoE prior only", "Hybrid (proposed)", "Ridge (no prior)", "Random forest (no prior)"]


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def s1():
    rng = np.random.default_rng(SEED)
    results = {}
    for scenario in ("linear", "nonlinear"):
        for offset in (0.0, 1.5):
            key = f"{scenario}|offset={offset}"
            curves = {m: {n: [] for n in N_GRID} for m in MODELS}
            transfer = {g: {m: [] for m in MODELS} for g in NEW_GEOMS}
            for _ in range(REPS):
                test_ops = sample_ops(rng, N_TEST)
                y_test = np.array([truth(BASE_GEOM, o, scenario, offset) for o in test_ops])  # noise-free truth
                pool_ops = sample_ops(rng, max(N_GRID))
                pool = [{**BASE_GEOM, **o,
                         "moisture_pct": truth(BASE_GEOM, o, scenario, offset) + rng.normal(0, LAB_SD)}
                        for o in pool_ops]
                for n in N_GRID:
                    for m in MODELS:
                        p = fit_predict(m, pool[:n], BASE_GEOM, test_ops)
                        if p is not None:
                            curves[m][n].append(rmse(p, y_test))
                # geometry transfer: train on 20 samples at base geometry, test on a new geometry
                for g, geom in NEW_GEOMS.items():
                    y_new = np.array([truth(geom, o, scenario, offset) for o in test_ops])
                    for m in MODELS:
                        transfer[g][m].append(rmse(fit_predict(m, pool[:20], geom, test_ops), y_new))
            results[key] = {
                "curves": {m: {str(n): [float(np.mean(v)), float(np.std(v))] if v else None
                               for n, v in curves[m].items()} for m in MODELS},
                "transfer_n20": {g: {m: [float(np.mean(v)), float(np.std(v))] for m, v in d.items()}
                                 for g, d in transfer.items()},
            }
            print(f"S1 {key}: done")
    (OUT / "s1_softsensor.json").write_text(json.dumps(results, indent=1))
    return results


# ----------------------------------------------------------------- S2 software benchmark
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def sample_payload(seq=0):
    from simulate import Machine
    m = Machine("WW-BENCH", dict(BASE_GEOM))
    p = m.step(2.0)
    p.pop("_true_moisture")
    p.update({"seq": seq, "boot_id": 1, "tx_ms": round(time.time() * 1000), "rssi": -60, "fw": "1.1.0"})
    return p


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))]


def s2():
    tmp = Path(tempfile.mkdtemp(prefix="wwbench_"))
    os.environ["WW_DB"] = str(tmp / "inproc.db")
    import main as srv  # noqa: E402  (opens the temporary DB)

    payload = sample_payload()
    size = len(json.dumps(payload, separators=(",", ":")).encode())
    # in-process ingest (validation, soft sensor, alarms, SQLite insert)
    t_in = []
    for i in range(5000):
        p = dict(payload, seq=i)
        t0 = time.perf_counter()
        srv.ingest(p)
        t_in.append((time.perf_counter() - t0) * 1000)
    # HTTP round trip on localhost through uvicorn
    port = free_port()
    env = dict(os.environ, WW_DB=str(tmp / "http.db"), WW_TOKEN="bench")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=str(ROOT / "server"), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/api/telemetry"
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        t_http = []
        t_start = time.perf_counter()
        for i in range(2000):
            body = json.dumps(dict(payload, seq=i)).encode()
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Content-Type": "application/json", "X-Token": "bench"})
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=5) as r:
                r.read()
            t_http.append((time.perf_counter() - t0) * 1000)
        wall = time.perf_counter() - t_start
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    cpu = platform.processor()
    try:
        cpu = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                             capture_output=True, text=True, timeout=20).stdout.strip() or cpu
    except Exception:
        pass
    res = {
        "host": {"cpu": cpu, "python": platform.python_version(), "os": platform.platform()},
        "payload_bytes": size,
        "payload_mb_per_day_at_2s": round(size * 43200 / 1e6, 2),
        "inproc_ingest_ms": {"n": len(t_in), "median": statistics.median(t_in), "p95": pct(t_in, 95),
                             "max": max(t_in)},
        "http_localhost_rtt_ms": {"n": len(t_http), "median": statistics.median(t_http), "p95": pct(t_http, 95),
                                  "max": max(t_http)},
        "http_sequential_msgs_per_s": round(len(t_http) / wall, 1),
        "machines_supported_at_2s_sequential": int(len(t_http) / wall * 2),
    }
    (OUT / "s2_benchmark.json").write_text(json.dumps(res, indent=1))
    print("S2:", json.dumps(res))
    return res


# ----------------------------------------------------------------- S3 alarm verification
def s3():
    import main as srv  # same temp DB as S2 (imported already)
    from simulate import Machine
    dt = 2.0
    warmup = 3600.0
    cases = {"heater:3": ("temp_low", 3), "leak:2": ("level_low", 2), "drum": ("omega_dev", None)}
    out = {"dt_s": dt, "warmup_excluded_s": warmup, "faults": {}, "normal": {}}
    for f, (code, bowl) in cases.items():
        delays = []
        for seed in range(20):
            m = Machine("WW-ALARM", dict(BASE_GEOM), seed=seed)
            kind, _, idx = f.partition(":")
            onset = warmup + 600.0 + 37.0 * seed
            m.faults.append((kind, int(idx) if idx else 0, onset))
            t_detect = None
            while m.t < onset + 7200:
                p = m.step(dt)
                p.pop("_true_moisture")
                al = srv.alerts_for(p, 57.0)
                if m.t >= onset and any(a["code"] == code and (bowl is None or a.get("bowl") == bowl) for a in al):
                    t_detect = m.t - onset
                    break
            delays.append(t_detect)
        ok = [d for d in delays if d is not None]
        out["faults"][f] = {"alert_code": code, "runs": len(delays), "detected": len(ok),
                            "delay_s_median": statistics.median(ok) if ok else None,
                            "delay_s_max": max(ok) if ok else None}
    # normal operation: count alerts after warm-up
    m = Machine("WW-NORMAL", dict(BASE_GEOM), seed=99)
    counts, steps = {}, 0
    while m.t < warmup + 8 * 3600:
        p = m.step(dt)
        p.pop("_true_moisture")
        if m.t < warmup:
            continue
        steps += 1
        for a in srv.alerts_for(p, 57.0):
            counts[a["code"]] = counts.get(a["code"], 0) + 1
    out["normal"] = {"hours": 8, "messages": steps, "alert_counts": counts}
    (OUT / "s3_alarms.json").write_text(json.dumps(out, indent=1))
    print("S3:", json.dumps(out))
    return out


# ----------------------------------------------------------------- figures
def figures(r1):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "font.family": "serif"})
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 2.25), sharey=True)
    style = {"DoE prior only": ("k", "--", None), "Hybrid (proposed)": ("C0", "-", "o"),
             "Ridge (no prior)": ("C1", "-", "s"), "Random forest (no prior)": ("C2", "-", "^")}
    for ax, key, title in zip(axes, ["linear|offset=1.5", "nonlinear|offset=1.5"], ["(a) linear", "(b) nonlinear"]):
        for m in PLOT_MODELS:
            pts = [(n, *r1[key]["curves"][m][str(n)]) for n in N_GRID if r1[key]["curves"][m][str(n)]]
            x = [p[0] + 0.5 for p in pts]
            c, ls, mk = style[m]
            ax.errorbar(x, [p[1] for p in pts], yerr=[p[2] for p in pts], color=c, ls=ls, marker=mk, ms=2.5,
                        lw=0.9, capsize=1.5, label=m)
        ax.set_xscale("log")
        ax.set_xticks([0.5, 1.5, 3.5, 10.5, 40.5])
        ax.set_xticklabels(["0", "1", "3", "10", "40"])
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("lab samples $n$")
        ax.grid(alpha=0.3, lw=0.4)
    axes[0].set_ylabel("RMSE (pp)")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=2, fontsize=6, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.80))
    fig.savefig(FIG / "sim_learning_curve.pdf")
    print("figure ->", FIG / "sim_learning_curve.pdf")


if __name__ == "__main__":
    r1 = s1()
    figures(r1)
    s2()
    s3()
    print("all results ->", OUT)
