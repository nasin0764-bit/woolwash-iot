import copy

import main as srv

H = {"X-Token": "test-token"}


def bowl1(payload, ntu):
    p = copy.deepcopy(payload)
    for b in p["bowls"]:
        b["turbidity_ntu"] = 300.0
    p["bowls"][0]["turbidity_ntu"] = ntu
    return p


def dirty(alerts):
    return any(a["code"] == "liquor_dirty" for a in alerts)


def test_dirty_liquor_debounce_and_hysteresis(payload):
    m = "WW-ADV"
    n = srv.LIMITS["turbidity_debounce_n"]
    for _ in range(n - 1):                                  # high, but not long enough yet
        assert not dirty(srv.alerts_for(bowl1(payload, 900), 57.0, m))
    assert dirty(srv.alerts_for(bowl1(payload, 900), 57.0, m))   # n-th message -> ON
    assert dirty(srv.alerts_for(bowl1(payload, 750), 57.0, m))   # between OFF and ON -> stays ON
    assert not dirty(srv.alerts_for(bowl1(payload, 650), 57.0, m))   # below OFF -> OFF


def test_single_spike_does_not_alarm(payload):
    m = "WW-SPIKE"
    assert not dirty(srv.alerts_for(bowl1(payload, 2000), 57.0, m))
    for _ in range(30):
        assert not dirty(srv.alerts_for(bowl1(payload, 400), 57.0, m))


def test_per_machine_limits_api(client, payload):
    assert client.put("/api/limits/WW-LIM", json={"turbidity_max_ntu": 850}).status_code == 401
    assert client.put("/api/limits/WW-LIM", json={"nonsense": 1}, headers=H).status_code == 400
    r = client.put("/api/limits/WW-LIM", json={"turbidity_max_ntu": 850, "turbidity_debounce_n": 1}, headers=H)
    assert r.status_code == 200 and r.json()["turbidity_max_ntu"] == 850
    assert client.get("/api/limits/WW-LIM").json()["turbidity_debounce_n"] == 1
    assert srv.LIMITS["turbidity_max_ntu"] == 800.0          # defaults unchanged
    assert not dirty(srv.alerts_for(bowl1(payload, 820), 57.0, "WW-LIM"))
    assert dirty(srv.alerts_for(bowl1(payload, 860), 57.0, "WW-LIM"))


def test_geometry_put_requires_token(client):
    assert client.put("/api/geometry/WW-G", json={"d_drum": 300}).status_code == 401
    assert client.put("/api/geometry/WW-G", json={"d_drum": 300}, headers=H).json()["d_drum"] == 300.0
