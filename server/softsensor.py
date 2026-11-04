"""
Residual-moisture soft sensor for the squeezing device.

Physics/experiment prior: the 2^3 full-factorial model from the dissertation
(Tuguzbayeva R.B., 2024, Table 3.10, significant terms only, verified by t-test):

    W = 57.31 + 0.81*X1 - 0.95*X2 + 0.30*X3      [% residual moisture]

    X1 = (d_hole - 2) / 1        mesh hole diameter, mm   (1..3)
    X2 = (D_drum - 250) / 50     squeeze drum diameter, mm (200..300)
    X3 = (gap - 3) / 1           drum-to-mesh gap, mm     (2..4)

The prior only knows the static geometry. On a running machine moisture also
depends on operating conditions (drum speed, feed rate, liquor temperature,
liquor dirtiness). Those effects are learned online as a ridge-regression
correction from laboratory (oven-dry) moisture samples entered by the operator:

    W_hat = W_prior(geometry) + w . phi(operating features) + c
"""
from __future__ import annotations

import numpy as np

B0, B1, B2, B3 = 57.31, 0.81, -0.95, 0.30

# nominal operating point (dissertation rational values)
NOMINAL = {
    "drum_omega": 16.0,      # rad/s
    "feed_kg_h": 425.0,      # kg/h (400-450)
    "temp_c": 55.0,          # degC, squeeze-side bowl
    "turbidity_ntu": 400.0,  # NTU
}
SCALE = {"drum_omega": 4.0, "feed_kg_h": 100.0, "temp_c": 10.0, "turbidity_ntu": 300.0}
FEATURES = list(NOMINAL.keys())


def coded(d_hole: float, d_drum: float, gap: float) -> tuple[float, float, float]:
    return (d_hole - 2.0) / 1.0, (d_drum - 250.0) / 50.0, (gap - 3.0) / 1.0


def prior(d_hole: float, d_drum: float, gap: float) -> float:
    x1, x2, x3 = coded(d_hole, d_drum, gap)
    return B0 + B1 * x1 + B2 * x2 + B3 * x3


def features(op: dict) -> np.ndarray:
    return np.array([(float(op.get(k, NOMINAL[k])) - NOMINAL[k]) / SCALE[k] for k in FEATURES])


class SoftSensor:
    def __init__(self, lam: float = 1.0):
        self.lam = lam
        self.w = np.zeros(len(FEATURES))
        self.c = 0.0
        self.n = 0
        self.rmse = None

    def fit(self, samples: list[dict]) -> None:
        """samples: dicts with geometry, operating features and measured 'moisture_pct'."""
        self.n = len(samples)
        if self.n < 3:
            self.w[:] = 0.0
            self.c = 0.0
            self.rmse = None
            return
        Phi = np.array([features(s) for s in samples])
        r = np.array([s["moisture_pct"] - prior(s["d_hole"], s["d_drum"], s["gap"]) for s in samples])
        A = np.hstack([Phi, np.ones((self.n, 1))])
        reg = self.lam * np.eye(A.shape[1])
        reg[-1, -1] = 1e-6  # do not shrink the bias
        theta = np.linalg.solve(A.T @ A + reg, A.T @ r)
        self.w, self.c = theta[:-1], float(theta[-1])
        pred = A @ theta
        self.rmse = float(np.sqrt(np.mean((pred - r) ** 2)))

    def predict(self, geom: dict, op: dict) -> float:
        p = prior(geom["d_hole"], geom["d_drum"], geom["gap"])
        return float(p + features(op) @ self.w + self.c)

    def info(self) -> dict:
        return {
            "prior": {"b0": B0, "b1": B1, "b2": B2, "b3": B3},
            "features": FEATURES,
            "weights": [round(float(v), 4) for v in self.w],
            "bias": round(self.c, 4),
            "n_samples": self.n,
            "train_rmse": None if self.rmse is None else round(self.rmse, 3),
        }
