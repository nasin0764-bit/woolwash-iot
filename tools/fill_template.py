"""
Fill IEEE_IoT_Factory_Validation_Template.xlsx from the WoolWash-IoT server.

Writes only the INPUT columns of the template; its own formulas (errors, received?,
latency, summary) stay untouched and recalculate when the file is opened in Excel.

    python fill_template.py TEMPLATE.xlsx OUTPUT.xlsx --machine WW-01 --hours 8 --trial A-2026-11-10

Simulated rows are refused unless --allow-sim is given; then every row is marked SIMULATED.
The template file itself is never modified.
"""
from __future__ import annotations

import argparse
import csv
import io
import shutil
import sys
import urllib.request
from pathlib import Path

import openpyxl

PACKET_ROWS = (6, 305)   # template rows reserved for packets
CALIB_ROWS = (6, 85)     # template rows reserved for calibration points


def get_csv(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=30) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


def num(v):
    try:
        return float(v) if "." in v else int(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("output")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--machine", default="WW-01")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--trial", default="")
    ap.add_argument("--allow-sim", action="store_true")
    a = ap.parse_args()

    tpl, out = Path(a.template).resolve(), Path(a.output).resolve()
    if tpl == out:
        sys.exit("Refusing to overwrite the template; give a different OUTPUT path.")

    base = f"{a.server}/api/validation/{a.machine}"
    q = f"?hours={a.hours}&trial={a.trial}"
    packets = get_csv(f"{base}/packets.csv{q}")
    calib = get_csv(f"{base}/calibration.csv?trial={a.trial}")

    sim = any("SIMULATED" in (r.get("Notes / reason lost") or "") for r in packets) or \
        any("SIMULATED" in (r.get("Reference instrument / notes") or "") for r in calib)
    if sim and not a.allow_sim:
        sys.exit("Server data contains SIMULATED rows. Use real device data, or pass --allow-sim "
                 "for a software test (never for the paper).")

    shutil.copyfile(tpl, out)
    wb = openpyxl.load_workbook(out)

    ws = wb["Packet delivery"]
    cap = PACKET_ROWS[1] - PACKET_ROWS[0] + 1
    for i, r in enumerate(packets[:cap]):
        row = PACKET_ROWS[0] + i
        ws.cell(row, 1, r["Trial ID"])
        ws.cell(row, 2, num(r["TX sequence #"]))
        ws.cell(row, 3, num(r["TX UTC epoch (ms)"]))
        ws.cell(row, 4, num(r["RX UTC epoch (ms)"]))
        ws.cell(row, 7, r["Gateway / link"])
        ws.cell(row, 8, r["Notes / reason lost"])

    ws = wb["Sensor calibration"]
    cap_c = CALIB_ROWS[1] - CALIB_ROWS[0] + 1
    for i, r in enumerate(calib[:cap_c]):
        row = CALIB_ROWS[0] + i
        ws.cell(row, 1, r["Trial ID"])
        ws.cell(row, 2, r["Sensor type"])
        ws.cell(row, 3, r["Sensor ID"])
        ws.cell(row, 4, r["UTC timestamp"])
        ws.cell(row, 5, num(r["Reference reading"]))
        ws.cell(row, 6, num(r["IoT reading"]))
        ws.cell(row, 10, r["Reference instrument / notes"])

    if sim:
        wb["START HERE"]["B4"] = "SOFTWARE TEST WITH SIMULATED DATA - NOT FOR PUBLICATION"
    wb.save(out)

    print(f"packets: {len(packets)} rows ({min(len(packets), cap)} written)")
    print(f"calibration: {len(calib)} rows ({min(len(calib), cap_c)} written)")
    if len(packets) > cap or len(calib) > cap_c:
        print("WARNING: more rows than the template holds. Use a shorter --hours window or extend the "
              "template ranges (and the Summary formulas) in Excel.")
    print("Water/energy batches: enter the meter readings by hand (they come from physical meters).")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
