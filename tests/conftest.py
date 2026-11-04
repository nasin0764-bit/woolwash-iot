import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for sub in ("server", "simulator", "tools"):
    sys.path.insert(0, str(ROOT / sub))

# the server opens its SQLite database at import time -> point it to a throw-away file first
_TMP = Path(tempfile.mkdtemp(prefix="ww_tests_"))
os.environ["WW_DB"] = str(_TMP / "test.db")
os.environ["WW_TOKEN"] = "test-token"


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


@pytest.fixture(scope="session")
def payload():
    from simulate import Machine
    m = Machine("WW-TEST", {"d_hole": 2.0, "d_drum": 250.0, "gap": 3.0})
    for _ in range(1800):          # 1 h of warm-up so temperatures are at set-point
        p = m.step(2.0)
    p.pop("_true_moisture")
    p["source"] = "device"
    return p
