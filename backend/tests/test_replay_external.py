# Read-only external checks for Replay MVP endpoints (safe: no POST replays, no heartbeats)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
REAL_SESSION = "9520beae-0705-49c2-aed9-32c64abb3cc1"

pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")


# Replay target for real session
def test_replay_target_real_session():
    r = requests.get(f"{BASE_URL}/api/sessions/{REAL_SESSION}/replay-target", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["sessionId"] == REAL_SESSION
    assert d["appPackage"] == "com.amts.sampleapp"
    assert d["stepCount"] == 1
    assert d["device"]["serial"] == "ZDEY45NRORWCF6N7"
    assert not any(k.startswith("_") for k in d)
    if d["compatible"]:
        assert d["appActivity"] == "com.amts.sampleapp.HomeActivity"
        assert d["device"]["model"] == "M2101K7BG"
        assert d["error"] is None
    else:
        assert d["error"]["code"] in ("AGENT_NOT_CONNECTED", "DEVICE_NOT_CONNECTED", "DEVICE_NOT_READY",
                                      "REPLAY_ALREADY_RUNNING", "RECORDING_ACTIVE")


# Replay target for unknown session
def test_replay_target_unknown_session():
    r = requests.get(f"{BASE_URL}/api/sessions/nope-xyz/replay-target", timeout=20)
    assert r.status_code == 404


# Unknown replay run
def test_get_replay_not_found():
    r = requests.get(f"{BASE_URL}/api/replays/does-not-exist", timeout=20)
    assert r.status_code == 404
    assert "REPLAY_NOT_FOUND" in r.text


# Replay history list
def test_list_replays_for_session():
    r = requests.get(f"{BASE_URL}/api/sessions/{REAL_SESSION}/replays", timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# Agent replay status requires token
def test_agent_replay_status_no_token():
    body = {"agentId": "x", "status": "RUNNING", "steps": []}
    r = requests.post(f"{BASE_URL}/api/agent/replays/x/status", json=body, timeout=20)
    assert r.status_code == 401


def test_agent_replay_status_bad_token():
    body = {"agentId": "x", "status": "RUNNING", "steps": []}
    r = requests.post(f"{BASE_URL}/api/agent/replays/x/status", json=body,
                      headers={"X-Agent-Token": "invalid-token-123"}, timeout=20)
    assert r.status_code == 401


def test_agent_command_result_no_token():
    r = requests.post(f"{BASE_URL}/api/agent/commands/x/result", json={"status": "FAILED"}, timeout=20)
    assert r.status_code == 401
