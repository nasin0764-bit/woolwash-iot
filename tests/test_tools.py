import csv
import shutil
import sys

import openpyxl
import pytest

import analyze_field as af
import fill_template as ft


@pytest.fixture()
def template(root, tmp_path):
    dst = tmp_path / "template.xlsx"
    shutil.copyfile(root / "docs" / "IEEE_IoT_Factory_Validation_Template.xlsx", dst)
    return dst


def fake_csv(packets, calib):
    def get_csv(url):
        return packets if "packets" in url else calib
    return get_csv


PK = [{"Trial ID": "T1", "TX sequence #": str(i), "TX UTC epoch (ms)": str(1000 + i * 2000),
       "RX UTC epoch (ms)": "" if i == 2 else str(1000 + i * 2000 + 50), "Received?": "", "Latency (ms)": "",
       "Gateway / link": "Wi-Fi/HTTP", "Notes / reason lost": "lost" if i == 2 else ""} for i in range(5)]
CAL = [{"Trial ID": "T1", "Sensor type": "Residual moisture soft sensor (%)", "Sensor ID": "WW-01",
        "UTC timestamp": "2026-11-10T08:00:00Z", "Reference reading": "58.0", "IoT reading": "57.5",
        "Reference instrument / notes": "oven"}]


def test_fill_template_keeps_formulas(monkeypatch, template, tmp_path):
    out = tmp_path / "filled.xlsx"
    monkeypatch.setattr(ft, "get_csv", fake_csv(PK, CAL))
    monkeypatch.setattr(sys, "argv", ["x", str(template), str(out), "--machine", "WW-01"])
    ft.main()
    ws = openpyxl.load_workbook(out)["Packet delivery"]
    assert ws.cell(6, 2).value == 0 and str(ws.cell(6, 5).value).startswith("=IF(")   # formula untouched
    assert ws.cell(8, 4).value is None                                                 # lost packet


def test_fill_template_refuses_simulated(monkeypatch, template, tmp_path):
    sim = [dict(PK[0], **{"Notes / reason lost": "SIMULATED"})]
    monkeypatch.setattr(ft, "get_csv", fake_csv(sim, []))
    monkeypatch.setattr(sys, "argv", ["x", str(template), str(tmp_path / "o.xlsx")])
    with pytest.raises(SystemExit):
        ft.main()


def test_fill_template_never_overwrites_template(monkeypatch, template):
    monkeypatch.setattr(sys, "argv", ["x", str(template), str(template)])
    with pytest.raises(SystemExit):
        ft.main()


def test_analyze_packets_and_calibration(monkeypatch, template, tmp_path):
    out = tmp_path / "filled.xlsx"
    monkeypatch.setattr(ft, "get_csv", fake_csv(PK, CAL))
    monkeypatch.setattr(sys, "argv", ["x", str(template), str(out)])
    ft.main()
    wb = openpyxl.load_workbook(out, data_only=True)
    pk, sim = af.analyze_packets(wb["Packet delivery"], False)
    assert not sim and pk["sent"] == 5 and pk["received"] == 4 and pk["pdr_pct"] == pytest.approx(80.0)
    assert pk["latency_ms"]["median"] == pytest.approx(50.0)
    cal, _ = af.analyze_calibration(wb["Sensor calibration"], False)
    m = cal["Residual moisture soft sensor (%)"]
    assert m["n"] == 1 and m["mae"] == pytest.approx(0.5) and m["bias"] == pytest.approx(-0.5)


def test_analyze_batches_and_faults(template, tmp_path):
    wb = openpyxl.load_workbook(template)
    ws = wb["Water energy batches"]
    for i, (mass, dw, de) in enumerate([(3000, 12, 30), (3200, 13, 31), (3100, 12.5, 29)]):
        for col, v in zip((1, 3, 4, 5, 6, 9, 10, 13), (f"B{i}", "A", mass, 100, 100 + dw, 500, 500 + de, 8)):
            ws.cell(6 + i, col, v)
    p = tmp_path / "b.xlsx"
    wb.save(p)
    res = af.analyze_batches(openpyxl.load_workbook(p, data_only=True)["Water energy batches"])
    lk = res["A"]["L/kg"]
    # 12 m3 / 3000 kg = 4.0 L/kg, 13/3200 = 4.0625, 12.5/3100 = 4.0323
    assert lk["n"] == 3 and lk["mean"] == pytest.approx((4.0 + 4.0625 + 4.032258) / 3, rel=1e-6)
    assert res["A"]["kWh/kg"]["mean"] == pytest.approx((30 / 3000 + 31 / 3200 + 29 / 3100) / 3, rel=1e-6)
    f = tmp_path / "faults.csv"
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fault_id", "type", "onset_utc", "first_alert_utc"])
        w.writerow([1, "heater", "2026-11-12T08:00:00Z", "2026-11-12T08:01:30Z"])
        w.writerow([2, "heater", "2026-11-12T09:00:00Z", ""])
    fr = af.analyze_faults(f)["heater"]
    assert fr["tests"] == 2 and fr["detected"] == 1 and fr["delay_s_median"] == 90


def test_metrics():
    m = af.metrics([1, 2, 3], [1, 2, 4])
    assert m["rmse"] == pytest.approx((1 / 3) ** 0.5) and m["mae"] == pytest.approx(1 / 3)
