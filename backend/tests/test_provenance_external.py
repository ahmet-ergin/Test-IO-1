# Provenance (environment_for) tests via public URL: fake agent heartbeats + session environment + export schema
import json
import os
import uuid

import jsonschema
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
SCHEMA = json.load(open("/app/shared/contracts/recording-session.v1.schema.json"))

CASES = [
    ("sim_true", {"available": True, "simulated": True, "version": "x"}, "R58N1234", "SM-G990", "SIMULATED_ADB"),
    ("sim_missing", {"available": True, "version": "x"}, "R58N1234", "SM-G990", None),
    ("sim_null", {"available": True, "simulated": None}, "R58N1234", "SM-G990", None),
    ("emu_serial", {"available": True, "simulated": False}, "emulator-5554", "Pixel", "EMULATOR"),
    ("emu_model", {"available": True, "simulated": False}, "ABC123", "sdk_gphone64_x86_64", "EMULATOR"),
    ("real", {"available": True, "simulated": False}, "R58N1234", "SM-G990", "REAL_DEVICE"),
    ("sim_true_emu", {"available": True, "simulated": True}, "emulator-5554", "Pixel", "SIMULATED_ADB"),
]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/settings/agent-token")
    assert r.status_code == 200
    return r.json()["token"]


@pytest.mark.parametrize("name,adb,serial,model,expected", CASES)
def test_environment(token, name, adb, serial, model, expected):
    aid = f"TEST_agent_{name}_{uuid.uuid4().hex[:6]}"
    serial = f"{serial}" if serial.startswith("emulator-") else f"TEST{uuid.uuid4().hex[:6]}"
    hb = {"agentId": aid, "name": aid, "version": "0.0.1", "adb": adb,
          "devices": [{"serial": serial, "state": "device", "model": model}]}
    h = {"X-Agent-Token": token}
    r = requests.post(f"{BASE_URL}/api/agent/heartbeat", json=hb, headers=h)
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE_URL}/api/sessions", json={"deviceSerial": serial})
    assert r.status_code == 200, r.text
    s = r.json()
    sid = s["id"]
    try:
        assert s["environment"] == expected
        assert s["agent_id"] == aid
        g = requests.get(f"{BASE_URL}/api/sessions/{sid}").json()
        assert g["environment"] == expected
        st = f"{BASE_URL}/api/agent/sessions/{sid}/state"
        assert requests.post(st, json={"status": "RECORDING"}, headers=h).status_code == 200
        assert requests.post(f"{BASE_URL}/api/sessions/{sid}/stop").status_code == 200
        r2 = requests.post(st, json={"status": "COMPLETED"}, headers=h)
        assert r2.status_code == 200, r2.text
        ex = requests.get(f"{BASE_URL}/api/sessions/{sid}/export")
        assert ex.status_code == 200, ex.text
        jsonschema.validate(ex.json(), SCHEMA)
        assert ex.json().get("environment", "MISSING") == expected
    finally:
        d = requests.delete(f"{BASE_URL}/api/sessions/{sid}")
        assert d.status_code in (200, 204)
        assert requests.get(f"{BASE_URL}/api/sessions/{sid}").status_code == 404
