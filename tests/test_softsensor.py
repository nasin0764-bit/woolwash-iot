import numpy as np
import pytest

from softsensor import SoftSensor, prior

G = {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0}


def sample(w, omega=16.0, feed=425.0):
    return {**G, "drum_omega": omega, "feed_kg_h": feed, "temp_c": 55.0, "turbidity_ntu": 400.0, "moisture_pct": w}


def test_prior_matches_dissertation_model():
    assert prior(2, 250, 3) == pytest.approx(57.31)
    # corners of the 2^3 design: b0 + b1 X1 + b2 X2 + b3 X3
    assert prior(1, 200, 2) == pytest.approx(57.31 - 0.81 + 0.95 - 0.30)
    assert prior(3, 300, 4) == pytest.approx(57.31 + 0.81 - 0.95 + 0.30)


def test_stage0_no_samples_is_prior():
    s = SoftSensor()
    s.fit([])
    assert s.predict(G, {}) == pytest.approx(57.31)


def test_stage1_offset_is_shrunk_towards_prior():
    s = SoftSensor()
    s.fit([sample(59.31), sample(59.31)])            # residual +2 pp each
    lam_c = (s.LAB_SD / s.TAU_C) ** 2
    assert s.c == pytest.approx(4.0 / (2 + lam_c))
    assert np.allclose(s.w, 0.0)                     # no operating weights before N_FULL samples


def test_stage2_learns_operating_effect():
    rng = np.random.default_rng(0)
    data = [sample(57.31 + 0.4 * (om - 16), omega=om) for om in rng.normal(16, 1, 40)]
    s = SoftSensor()
    s.fit(data)
    assert s.n == 40 and s.w[0] > 0                  # drum-speed weight has the right sign
    assert s.predict(G, {"drum_omega": 18.0}) > s.predict(G, {"drum_omega": 14.0})


def test_prior_transfers_to_new_geometry():
    s = SoftSensor()
    s.fit([sample(58.0) for _ in range(6)])
    new = {"d_hole": 2.0, "d_drum": 300.0, "gap": 3.0}
    assert s.predict(new, {}) - s.predict(G, {}) == pytest.approx(-0.95, abs=1e-9)
