"""
Field-validation analysis for Section VII (factory IoT results) of the paper.

Inputs (all REAL factory data):
  * the filled IEEE_IoT_Factory_Validation_Template.xlsx
      - "Sensor calibration"   reference vs IoT reading (incl. soft-sensor rows from fill_template.py)
      - "Packet delivery"      one row per transmitted packet
      - "Water energy batches" metered water/energy per batch or shift, with Mode
  * the WoolWash server (lab samples with operating features) for the 4-model soft-sensor comparison
  * optional --faults CSV: fault_id,type,onset_utc,first_alert_utc   (supervised fault tests)

Outputs (results/field/ by default):
  summary.json and LaTeX snippets tab_calibration.tex, tab_softsensor.tex, tab_network.tex,
  tab_resources.tex, tab_faults.tex, ready for \\input{} in Section VII.

    python tools/analyze_field.py filled.xlsx --server http://127.0.0.1:8000 --machine WW-01
    python tools/analyze_field.py filled.xlsx --no-server            # skip the model comparison

Rows marked SIMULATED are refused unless --allow-sim; then tables are watermarked "SIMULATED - NOT FOR
PUBLICATION" and the output folder must not be results/field.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
from softsensor import SoftSensor, prior, FEATURES  # noqa: E402

SIM_MARK = "SIMULATED"


# ----------------------------------------------------------------- helpers
def tcrit(df: int) -> float:
    try:
        from scipy import stats
        return float(stats.t.ppf(0.975, df))
    except Exception:  # scipy missing: normal approximation
        return 1.96


def mean_sd_ci(v):
    v = [float(x) for x in v]
    n = len(v)
    if n == 0:
        return {"n": 0}
    m = statistics.fmean(v)
    sd = statistics.stdev(v) if n > 1 else float("nan")
    half = tcrit(n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
    return {"n": n, "mean": m, "sd": sd, "ci95": [m - half, m + half]}


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = p - y
    ss = float(((y - y.mean()) ** 2).sum())
    return {"n": int(len(y)), "rmse": float(np.sqrt((e ** 2).mean())), "mae": float(np.abs(e).mean()),
            "bias": float(e.mean()), "r2": float(1 - (e ** 2).sum() / ss) if ss > 0 else float("nan")}


def pct(v, q):
    v = sorted(v)
    if not v:
        return float("nan")
    k = (len(v) - 1) * q / 100
    f, c = math.floor(k), math.ceil(k)
    return v[f] + (v[c] - v[f]) * (k - f)


def f(x, d=2):
    return "--" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def rows(ws, first=6, ncols=16):
    for r in ws.iter_rows(min_row=first, max_col=ncols, values_only=True):
        if r and any(v not in (None, "") for v in r[:4]):
            yield r


def latex_table(caption, label, header, body, sim, colspec=None):
    if sim:
        caption = f"[{SIM_MARK} - NOT FOR PUBLICATION] " + caption
    colspec = colspec or "l" + "c" * (len(header) - 1)
    out = ["\\begin{table}[t]\\centering\\footnotesize", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
           f"\\begin{{tabular}}{{{colspec}}}\\toprule", " & ".join(header) + "\\\\\\midrule"]
    out += [" & ".join(str(c) for c in r) + "\\\\" for r in body]
    out += ["\\bottomrule\\end{tabular}\\end{table}", ""]
    return "\n".join(out)


# ----------------------------------------------------------------- analyses
def analyze_calibration(ws, sim_ok):
    groups, sim = {}, False
    for r in rows(ws, ncols=11):
        _, stype, sid, ts, ref, iot = r[:6]
        note = str(r[9] or "")
        if SIM_MARK in note.upper():
            sim = True
            if not sim_ok:
                continue
        if ref is None or iot is None:
            continue
        groups.setdefault(str(stype), []).append((float(ref), float(iot)))
    res = {k: metrics([a for a, _ in v], [b for _, b in v]) for k, v in groups.items()}
    return res, sim


def csv_packet_rows(paths):
    """Rows of one or more server packets.csv exports (GET /api/validation/{id}/packets.csv) in the column
    order of the template's 'Packet delivery' sheet. Use this when a trial has more packets than the
    template holds (300 rows; one 8-h shift at 2 s is 14 400 packets)."""
    def num(v):
        return None if v in (None, "") else float(v)
    out = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.reader(fh):
                if not r or r[0] == "Trial ID":
                    continue
                out.append((r[0], num(r[1]), num(r[2]), num(r[3]), None, None, r[6], r[7]))
    return out


def analyze_packets(ws, sim_ok, csv_rows=None):
    sent = recv = neg = 0
    lat = []
    allrows = csv_rows if csv_rows is not None else list(rows(ws, ncols=8))
    # a trial with ANY simulated row is simulated as a whole (its lost-packet rows carry no SIM mark)
    sim_trials = {r[0] for r in allrows if SIM_MARK in str(r[7] or "").upper()}
    sim = bool(sim_trials)
    for r in allrows:
        tid, seq, tx, rx = r[:4]
        if tid in sim_trials and not sim_ok:
            continue
        if seq is None:
            continue
        sent += 1
        if rx not in (None, ""):
            recv += 1
            if tx not in (None, ""):
                d = float(rx) - float(tx)
                if d < 0:
                    neg += 1
                else:
                    lat.append(d)
    res = {"sent": sent, "received": recv, "lost": sent - recv,
           "pdr_pct": 100 * recv / sent if sent else float("nan"),
           "latency_ms": {"n": len(lat), "median": pct(lat, 50), "p95": pct(lat, 95),
                          "max": max(lat) if lat else float("nan")},
           "negative_latencies": neg}
    return res, sim


def analyze_batches(ws):
    by_mode = {}
    for r in rows(ws, ncols=16):
        bid, date, mode, mass, ws0, ws1, _, _, e0, e1, _, _, hours = r[:13]
        if mass in (None, "") or float(mass) <= 0:
            continue
        d = by_mode.setdefault(str(mode or "unspecified"), {"L/kg": [], "kWh/kg": [], "kg/h": []})
        if ws0 not in (None, "") and ws1 not in (None, "") and float(ws1) >= float(ws0):
            d["L/kg"].append(1000 * (float(ws1) - float(ws0)) / float(mass))
        if e0 not in (None, "") and e1 not in (None, "") and float(e1) >= float(e0):
            d["kWh/kg"].append((float(e1) - float(e0)) / float(mass))
        if hours not in (None, "") and float(hours) > 0:
            d["kg/h"].append(float(mass) / float(hours))
    res = {m: {k: mean_sd_ci(v) for k, v in d.items()} for m, d in by_mode.items()}
    modes = list(by_mode)
    if len(modes) >= 2:
        try:
            from scipy import stats
            a, b = modes[0], modes[1]
            res["_welch"] = {}
            for k in ("L/kg", "kWh/kg"):
                x, y = by_mode[a][k], by_mode[b][k]
                if len(x) > 1 and len(y) > 1:
                    t, p = stats.ttest_ind(x, y, equal_var=False)
                    res["_welch"][k] = {"modes": [a, b], "t": float(t), "p": float(p)}
        except Exception:
            pass
    return res


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def analyze_models(server, machine, test_frac_days, sim_ok):
    """Day-separated comparison: the last days (by calendar date) form the held-out test set."""
    lab = fetch(f"{server}/api/lab/{machine}")
    geom = fetch(f"{server}/api/model/{machine}")["geometry"]
    sim = any(SIM_MARK in (s.get("note") or "").upper() for s in lab)
    if sim and not sim_ok:
        return {"error": "lab samples contain SIMULATED rows"}, sim
    samples = [{**geom, **s["op"], "moisture_pct": s["moisture_pct"],
                "day": datetime.fromtimestamp(s["ts"], timezone.utc).date().isoformat()}
               for s in lab if s.get("op")]
    days = sorted({s["day"] for s in samples})
    if len(days) < 2:
        return {"error": f"need samples from >=2 days for a day-separated split, have {len(days)}"}, sim
    n_test_days = max(1, round(len(days) * test_frac_days))
    test_days = set(days[-n_test_days:])
    tr = [s for s in samples if s["day"] not in test_days]
    te = [s for s in samples if s["day"] in test_days]
    y = [s["moisture_pct"] for s in te]
    X = lambda S: np.array([[s[k] for k in FEATURES] for s in S])  # noqa: E731
    out = {"train_n": len(tr), "test_n": len(te), "train_days": len(days) - n_test_days, "test_days": n_test_days}
    out["DoE prior only"] = metrics(y, [prior(geom["d_hole"], geom["d_drum"], geom["gap"])] * len(te))
    ss = SoftSensor()
    ss.fit(tr)
    out["Hybrid (proposed)"] = metrics(y, [ss.predict(geom, s) for s in te])
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestRegressor
    ytr = [s["moisture_pct"] for s in tr]
    if len(tr) >= 3:
        sc = StandardScaler().fit(X(tr))
        out["Ridge (no prior)"] = metrics(y, Ridge(alpha=1.0).fit(sc.transform(X(tr)), ytr).predict(sc.transform(X(te))))
        rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=0).fit(X(tr), ytr)
        out["Random forest (no prior)"] = metrics(y, rf.predict(X(te)))
    return out, sim


def analyze_faults(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            on = datetime.fromisoformat(r["onset_utc"].replace("Z", "+00:00"))
            d = out.setdefault(r["type"], {"tests": 0, "detected": 0, "delays_s": []})
            d["tests"] += 1
            if r.get("first_alert_utc"):
                al = datetime.fromisoformat(r["first_alert_utc"].replace("Z", "+00:00"))
                d["detected"] += 1
                d["delays_s"].append((al - on).total_seconds())
    for d in out.values():
        v = d.pop("delays_s")
        d["delay_s_median"] = statistics.median(v) if v else float("nan")
        d["delay_s_max"] = max(v) if v else float("nan")
    return out


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--machine", default="WW-01")
    ap.add_argument("--no-server", action="store_true")
    ap.add_argument("--faults", default=None)
    ap.add_argument("--test-frac-days", type=float, default=0.25)
    ap.add_argument("--out", default=str(ROOT / "results" / "field"))
    ap.add_argument("--allow-sim", action="store_true")
    ap.add_argument("--packets-csv", nargs="+", default=None,
                    help="server packets.csv export(s) to use instead of the template's 'Packet delivery' sheet")
    a = ap.parse_args()

    out = Path(a.out).resolve()
    if a.allow_sim and out == (ROOT / "results" / "field").resolve():
        sys.exit("--allow-sim output must not go to results/field (publication folder). Use --out <temp dir>.")
    out.mkdir(parents=True, exist_ok=True)

    import openpyxl
    wb = openpyxl.load_workbook(a.workbook, data_only=True)
    summary, sim_any = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, False

    cal, s1 = analyze_calibration(wb["Sensor calibration"], a.allow_sim)
    pk, s2 = analyze_packets(wb["Packet delivery"], a.allow_sim,
                             csv_packet_rows(a.packets_csv) if a.packets_csv else None)
    bt = analyze_batches(wb["Water energy batches"])
    sim_any = s1 or s2
    summary.update({"calibration": cal, "packets": pk, "batches": bt})
    if (s1 or s2) and not a.allow_sim:
        print("NOTE: SIMULATED rows were found and EXCLUDED.")

    if not a.no_server:
        try:
            mod, s3 = analyze_models(a.server, a.machine, a.test_frac_days, a.allow_sim)
            sim_any = sim_any or s3
            summary["models"] = mod
        except Exception as e:  # server not reachable
            summary["models"] = {"error": str(e)}
    if a.faults:
        summary["faults"] = analyze_faults(a.faults)
    summary["contains_simulated"] = bool(sim_any and a.allow_sim)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    sim = summary["contains_simulated"]

    # ---- LaTeX snippets
    body = [[k.replace("%", "\\%"), v["n"], f(v["mae"]), f(v["rmse"]), f(v["bias"])] for k, v in cal.items()]
    (out / "tab_calibration.tex").write_text(latex_table(
        "Sensor calibration against reference instruments", "tab:fieldcal",
        ["Sensor", "$n$", "MAE", "RMSE", "Bias"], body or [["--"] * 5], sim, "p{0.42\\columnwidth}cccc"), "utf-8")

    m = summary.get("models", {})
    if "error" not in m and m:
        body = [[k, f(m[k]["rmse"]), f(m[k]["mae"]), f(m[k]["r2"])] for k in
                ("DoE prior only", "Hybrid (proposed)", "Ridge (no prior)", "Random forest (no prior)") if k in m]
        cap = (f"Held-out residual-moisture prediction (pp); train {m['train_n']} samples / {m['train_days']} days, "
               f"test {m['test_n']} samples / {m['test_days']} later day(s)")
        (out / "tab_softsensor.tex").write_text(latex_table(cap, "tab:fieldss", ["Model", "RMSE", "MAE", "$R^2$"],
                                                            body, sim), "utf-8")

    L = pk["latency_ms"]
    body = [["Packets sent / received", f"{pk['sent']} / {pk['received']}"],
            ["Packet delivery (\\%)", f(pk["pdr_pct"])],
            ["Latency median / p95 (ms)", f"{f(L['median'], 0)} / {f(L['p95'], 0)}"],
            ["Negative latencies (clock check)", pk["negative_latencies"]]]
    (out / "tab_network.tex").write_text(latex_table("Communication performance", "tab:fieldnet",
                                                     ["Measure", "Value"], body, sim), "utf-8")

    body = []
    for mode, d in bt.items():
        if mode.startswith("_"):
            continue
        for k in ("kWh/kg", "L/kg", "kg/h"):
            s = d[k]
            if s.get("n"):
                body.append([mode, k, s["n"], f"{f(s['mean'], 3)} $\\pm$ {f(s['sd'], 3)}",
                             f"[{f(s['ci95'][0], 3)}, {f(s['ci95'][1], 3)}]"])
    (out / "tab_resources.tex").write_text(latex_table("Metered resource use per batch (mean $\\pm$ SD, 95\\% CI)",
                                                       "tab:fieldres", ["Mode", "Indicator", "$n$", "Mean $\\pm$ SD",
                                                                        "95\\% CI"], body or [["--"] * 5], sim),
                                           "utf-8")
    if "faults" in summary:
        body = [[k, f"{v['detected']}/{v['tests']}", f(v["delay_s_median"], 0), f(v["delay_s_max"], 0)]
                for k, v in summary["faults"].items()]
        (out / "tab_faults.tex").write_text(latex_table("Supervised fault tests", "tab:fieldfault",
                                                        ["Fault", "Detected", "Median delay (s)", "Max delay (s)"],
                                                        body, sim), "utf-8")
    print(json.dumps({k: summary[k] for k in summary if k in ("packets", "contains_simulated")}, default=float))
    print("outputs ->", out)


if __name__ == "__main__":
    main()
