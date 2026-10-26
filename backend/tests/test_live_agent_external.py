# Live flow via SIMULATED agent (requires agent running with fake-adb; run with AMTS_AGENT_RUNNING=1)
import json
import os
import time
import pytest
import requests
from pathlib import Path

if os.environ.get("AMTS_AGENT_RUNNING") != "1":
    pytest.skip("simulated agent not running", allow_module_level=True)

import jsonschema  # noqa: E402

BASE = "http://localhost:8001/api"
SCHEMA = json.loads(Path("/app/shared/contracts/recording-session.v1.schema.json").read_text())


def _wait(sid, statuses, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        s = requests.get(f"{BASE}/sessions/{sid}").json()
        if s["status"] in statuses:
            return s
        time.sleep(0.5)
    return s


def test_saved_simulated_session_exports_valid():
    sims = [s for s in requests.get(f"{BASE}/sessions").json() if not s["demo"] and s["status"] == "COMPLETED"]
    assert sims
    doc = requests.get(f"{BASE}/sessions/{sims[0]['id']}/export").json()
    jsonschema.validate(doc, SCHEMA)


def test_invalid_transitions_live():
    r = requests.post(f"{BASE}/sessions", json={"deviceSerial": "FAKE-0001", "name": "SIMULATED TEST_transitions"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["status"] == "STARTING"
    p = requests.post(f"{BASE}/sessions/{sid}/pause")
    assert p.status_code == 409 and "INVALID_STATE_TRANSITION" in p.text
    r2 = requests.post(f"{BASE}/sessions", json={"deviceSerial": "FAKE-0001"})
    assert r2.status_code == 409 and "SESSION_ALREADY_ACTIVE" in r2.text
    assert requests.delete(f"{BASE}/sessions/{sid}").status_code == 409
    _wait(sid, ["RECORDING"])
    assert requests.post(f"{BASE}/sessions/{sid}/resume").status_code == 409
    assert requests.post(f"{BASE}/sessions/{sid}/stop").status_code == 200
    s = _wait(sid, ["COMPLETED", "FAILED"])
    assert s["status"] == "COMPLETED"
    for op in ("pause", "resume", "stop"):
        assert requests.post(f"{BASE}/sessions/{sid}/{op}").status_code == 409
    assert requests.delete(f"{BASE}/sessions/{sid}").status_code == 200
    assert requests.get(f"{BASE}/sessions/{sid}").status_code == 404
