import copy
import csv
import io

H = {"X-Token": "test-token"}


def post(client, p):
    return client.post("/api/telemetry", json=p, headers=H)


def test_token_required(client, payload):
    assert client.post("/api/telemetry", json=payload).status_code == 401
    assert client.post("/api/telemetry", json=payload, headers={"X-Token": "wrong"}).status_code == 401


def test_ingest_and_latest(client, payload):
    p = copy.deepcopy(payload)
    p["machine_id"] = "WW-T1"
    r = post(client, p)
    assert r.status_code == 200 and 50 < r.json()["moisture_pred"] < 65
    latest = client.get("/api/latest/WW-T1").json()
    assert latest["data"]["machine_id"] == "WW-T1"
    assert any(m["id"] == "WW-T1" for m in client.get("/api/machines").json())


def test_alerts(client, payload):
    p = copy.deepcopy(payload)
    p["machine_id"] = "WW-T2"
    p["bowls"][2]["temp_c"] = 20.0          # heater failure bowl 3
    p["bowls"][1]["level_cm"] = 10.0        # low level bowl 2
    p["squeeze"][0]["drum_omega"] = 10.0    # drum slip
    codes = {(a["code"], a.get("bowl")) for a in post(client, p).json()["alerts"]}
    assert ("temp_low", 3) in codes and ("level_low", 2) in codes and ("omega_dev", None) in codes


def test_lab_sample_stores_out_of_sample_prediction(client, payload):
    p = copy.deepcopy(payload)
    p["machine_id"] = "WW-T3"
    post(client, p)
    r = client.post("/api/lab", json={"machine": "WW-T3", "moisture_pct": 59.0, "note": "unit test"})
    assert r.status_code == 200 and r.json()["model"]["n_samples"] == 1
    rows = list(csv.DictReader(io.StringIO(client.get("/api/validation/WW-T3/calibration.csv").text)))
    assert len(rows) == 1
    assert float(rows[0]["Reference reading"]) == 59.0
    assert abs(float(rows[0]["IoT reading"]) - 57.31) < 3     # prediction made BEFORE training on it


def test_packet_export_detects_gaps(client, payload):
    for seq in (0, 1, 2, 5, 6):              # 3 and 4 lost
        p = copy.deepcopy(payload)
        p.update({"machine_id": "WW-T4", "seq": seq, "boot_id": 7, "tx_ms": 1793800000000 + seq * 2000})
        post(client, p)
    rows = list(csv.DictReader(io.StringIO(client.get("/api/validation/WW-T4/packets.csv").text)))
    assert [int(r["TX sequence #"]) for r in rows] == [0, 1, 2, 3, 4, 5, 6]
    lost = [r for r in rows if r["RX UTC epoch (ms)"] == ""]
    assert [int(r["TX sequence #"]) for r in lost] == [3, 4]


def test_csv_export(client, payload):
    p = copy.deepcopy(payload)
    p["machine_id"] = "WW-T5"
    post(client, p)
    text = client.get("/api/export/WW-T5.csv").text
    assert text.startswith("ts,source,power_w") and len(text.splitlines()) == 2


def test_counter_increase_survives_reboot_and_loss():
    from main import counter_increase
    # boot 1: 0 -> 10 with a lost packet (no 6), reboot: counter restarts at 0, boot 2: 1 -> 4
    s = [(1, 0.0), (1, 2.0), (1, 4.0), (1, 8.0), (1, 10.0), (2, 1.0), (2, 2.5), (2, 4.0)]
    assert counter_increase(s) == 14.0          # naive last-first would give 4.0
    # older firmware without boot_id: a decrease is treated as a restart
    assert counter_increase([(None, 5.0), (None, 9.0), (None, 2.0), (None, 3.0)]) == 4.0 + 2.0 + 1.0


def test_kpis_across_reboot(client, payload):
    import main
    t0 = 1_790_000_000.0
    for i, (boot, e, w, f) in enumerate([(1, 0.0, 0, 0.0), (1, 1.0, 100, 10.0), (1, 2.0, 200, 20.0),
                                         (2, 0.5, 50, 5.0), (2, 1.5, 150, 15.0)]):
        p = copy.deepcopy(payload)
        p.update({"machine_id": "WW-T6", "ts": t0 + 2 * i, "seq": i, "boot_id": boot,
                  "energy_kwh": e, "water_total_l": w, "feed_total_kg": f})
        post(client, p)
    k = main.kpis("WW-T6", t0 - 1)
    assert k["energy_kwh"] == 3.5 and k["water_l"] == 350 and k["feed_kg"] == 35.0
