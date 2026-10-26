# External-URL regression tests for AMTS Phase 1 (no-agent state, demo sessions, steps, settings, audit, retention)
import json
import os
import pytest
import requests
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        for line in Path("/app/frontend/.env").read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                url = line.split("=", 1)[1]
    return url.rstrip("/")


BASE = _base() + "/api"
SCHEMA = json.loads(Path("/app/shared/contracts/recording-session.v1.schema.json").read_text())
pytestmark = pytest.mark.skipif(os.environ.get("AMTS_AGENT_RUNNING") == "1", reason="needs no-agent state")


@pytest.fixture(scope="module")
def demo():
    r = requests.post(f"{BASE}/demo/sessions", timeout=30)
    assert r.status_code == 200, r.text
    s = r.json()
    yield s
    requests.delete(f"{BASE}/sessions/{s['id']}", timeout=30)


# Health / status / devices (no agent)
def test_health():
    r = requests.get(f"{BASE}/health", timeout=15)
    assert r.status_code == 200


def test_status_no_agent():
    d = requests.get(f"{BASE}/status", timeout=15).json()
    assert d["agentConnected"] is False
    assert d["onlineDevices"] == 0


def test_devices_no_agent():
    d = requests.get(f"{BASE}/devices", timeout=15).json()
    assert d["agentConnected"] is False
    assert d["message"] == "Local Recorder Agent is not connected."
    assert d["devices"] == []


def test_start_session_without_agent_503():
    r = requests.post(f"{BASE}/sessions", json={"deviceSerial": "FAKE-0001"}, timeout=15)
    assert r.status_code == 503
    assert "AGENT_NOT_CONNECTED" in r.text


def test_refresh_devices_without_agent_503():
    assert requests.post(f"{BASE}/devices/refresh", timeout=15).status_code == 503


# Demo session + export contract
def test_demo_session_labeled(demo):
    assert demo["demo"] is True and demo["status"] == "COMPLETED"
    assert "DEMO" in demo["name"]
    evs = requests.get(f"{BASE}/sessions/{demo['id']}/events", timeout=15).json()
    assert len(evs) == 6 and all(e["captureSource"] == "DEMO" for e in evs)
    pin = [e for e in evs if e["action"] == "INPUT_TEXT" and e["inputValue"]["masked"]]
    assert pin and pin[0]["inputValue"]["value"] is None


def test_demo_export_valid_schema(demo):
    r = requests.get(f"{BASE}/sessions/{demo['id']}/export", timeout=15)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    if jsonschema:
        jsonschema.validate(r.json(), SCHEMA)


def test_demo_control_409(demo):
    for op in ("stop", "pause", "resume"):
        r = requests.post(f"{BASE}/sessions/{demo['id']}/{op}", timeout=15)
        assert r.status_code == 409, (op, r.text)


# Steps CRUD / reorder
def test_step_patch_delete_reorder(demo):
    sid = demo["id"]
    steps = requests.get(f"{BASE}/sessions/{sid}/steps", timeout=15).json()
    assert len(steps) >= 5
    st = steps[1]
    r = requests.patch(f"{BASE}/steps/{st['id']}", json={"name": "TEST_renamed", "description": "d",
                                                          "verification": True}, timeout=15)
    assert r.status_code == 200 and r.json()["name"] == "TEST_renamed" and r.json()["verification"] is True
    bad = requests.patch(f"{BASE}/steps/{st['id']}", json={"selectedLocatorIndex": 99}, timeout=15)
    assert bad.status_code == 422
    assert requests.delete(f"{BASE}/steps/{steps[0]['id']}", timeout=15).status_code == 200
    after = requests.get(f"{BASE}/sessions/{sid}/steps", timeout=15).json()
    assert len(after) == len(steps) - 1
    assert len(requests.get(f"{BASE}/sessions/{sid}/events", timeout=15).json()) == 6
    order = [s["id"] for s in after][::-1]
    r = requests.post(f"{BASE}/sessions/{sid}/steps/reorder", json={"order": order}, timeout=15)
    assert r.status_code == 200 and "warning" in r.json()
    assert [s["id"] for s in requests.get(f"{BASE}/sessions/{sid}/steps", timeout=15).json()] == order
    r = requests.post(f"{BASE}/sessions/{sid}/steps/reorder", json={"order": order[:-1]}, timeout=15)
    assert r.status_code == 422


def test_step_not_found():
    assert requests.patch(f"{BASE}/steps/nope", json={"name": "x"}, timeout=15).status_code == 404
    assert requests.delete(f"{BASE}/steps/nope", timeout=15).status_code == 404


def test_session_not_found():
    assert requests.get(f"{BASE}/sessions/nope", timeout=15).status_code == 404


# Settings / token / audit / retention
def test_settings_roundtrip():
    s = requests.get(f"{BASE}/settings", timeout=15).json()
    assert "agent_token_hash" not in s
    orig = s["capture_interval_ms"]
    r = requests.put(f"{BASE}/settings", json={"capture_interval_ms": orig + 100}, timeout=15)
    assert r.status_code == 200 and r.json()["capture_interval_ms"] == orig + 100
    requests.put(f"{BASE}/settings", json={"capture_interval_ms": orig}, timeout=15)


def test_settings_invalid_interval():
    r = requests.put(f"{BASE}/settings", json={"capture_interval_ms": -5}, timeout=15)
    assert r.status_code == 422


def test_token_rotation_invalidates_old():
    t1 = requests.post(f"{BASE}/settings/agent-token", timeout=15).json()["token"]
    hb = {"agentId": "TEST-agent", "name": "TEST", "version": "0", "os": "x",
          "adb": {"available": False}, "devices": []}
    t2 = requests.post(f"{BASE}/settings/agent-token", timeout=15).json()["token"]
    assert t1 != t2
    r = requests.post(f"{BASE}/agent/heartbeat", headers={"X-Agent-Token": t1}, json=hb, timeout=15)
    assert r.status_code == 401
    r = requests.post(f"{BASE}/agent/heartbeat", headers={"X-Agent-Token": "bad"}, json=hb, timeout=15)
    assert r.status_code == 401


def test_audit_logs():
    logs = requests.get(f"{BASE}/audit-logs", timeout=15).json()
    assert isinstance(logs, list) and logs
    assert any(l.get("action") == "AGENT_TOKEN_ROTATED" or "AGENT_TOKEN_ROTATED" in json.dumps(l) for l in logs)


def test_retention_purge():
    r = requests.post(f"{BASE}/retention/purge", timeout=30)
    assert r.status_code == 200 and "deleted" in r.json()
