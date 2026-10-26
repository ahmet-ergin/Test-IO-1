import uuid
from datetime import datetime, timezone, timedelta
from conftest import device, heartbeat
from core.db import db
from services.agent_service import reconcile

PKG = "com.amts.sampleapp"
SERIAL = "REPLAY-DEV-1"
AGENT = "agent-replay"


def _ev(sid, seq, action="TAP", rid="com.amts.sampleapp:id/transferButton"):
    return {"eventId": str(uuid.uuid4()), "sessionId": sid, "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(), "action": action, "deviceId": SERIAL,
            "packageName": PKG, "activity": "com.amts.sampleapp.HomeActivity", "captureSource": "HYBRID",
            "confidence": 0.95, "uncertain": False, "limitations": [],
            "element": {"resourceId": rid, "text": "TRANSFER", "className": "android.widget.Button"},
            "coordinates": {"x": 10, "y": 20}}


def _hb(client, token, devices=None):
    return heartbeat(client, token, [device(SERIAL)] if devices is None else devices, agent_id=AGENT)


def _recorded(client, token, actions=("TAP",), pkg=PKG, save=True):
    _hb(client, token)
    sid = client.post("/api/sessions", json={"deviceSerial": SERIAL, "packageFilter": pkg}).json()["id"]
    _hb(client, token)
    h = {"X-Agent-Token": token}
    assert client.post(f"/api/agent/sessions/{sid}/state", headers=h,
                       json={"status": "RECORDING", "packageName": pkg}).status_code == 200
    evs = [_ev(sid, i + 1, a) for i, a in enumerate(actions)]
    for e in evs:
        e["packageName"] = pkg
    assert client.post(f"/api/agent/sessions/{sid}/events", headers=h, json={"events": evs}).json()["accepted"] == len(evs)
    client.post(f"/api/sessions/{sid}/stop")
    _hb(client, token)
    client.post(f"/api/agent/sessions/{sid}/state", headers=h, json={"status": "COMPLETED"})
    if save:
        client.patch(f"/api/sessions/{sid}", json={"saved": True})
    return sid


def _upd(client, token, run_id, **body):
    return client.post(f"/api/agent/replays/{run_id}/status", headers={"X-Agent-Token": token},
                       json={"agentId": AGENT, **body})


def test_replay_pass_flow(client, token):
    sid = _recorded(client, token)
    t = client.get(f"/api/sessions/{sid}/replay-target").json()
    assert t["compatible"] and t["appActivity"] == "com.amts.sampleapp.HomeActivity" and t["device"]["serial"] == SERIAL
    run = client.post(f"/api/sessions/{sid}/replays").json()
    assert run["status"] == "QUEUED" and run["steps"][0]["locators"][0]["strategy"] == "RESOURCE_ID"
    assert all(loc["strategy"] != "COORDINATES" for loc in run["steps"][0]["locators"])
    # second replay on same device is blocked
    assert client.post(f"/api/sessions/{sid}/replays").json()["error"]["code"] == "REPLAY_ALREADY_RUNNING"
    # recording blocked while replay active
    assert client.post("/api/sessions", json={"deviceSerial": SERIAL}).json()["error"]["code"] == "REPLAY_ACTIVE"
    cmds = _hb(client, token).json()["commands"]
    c = [c for c in cmds if c["type"] == "START_REPLAY"][0]
    assert c["payload"]["runId"] == run["id"] and c["payload"]["appPackage"] == PKG
    step = run["steps"][0]["stepId"]
    assert _upd(client, token, run["id"], status="PASSED").status_code == 409  # QUEUED -> PASSED invalid
    other = client.post(f"/api/agent/replays/{run['id']}/status", headers={"X-Agent-Token": token},
                        json={"agentId": "someone-else", "status": "RUNNING"})
    assert other.status_code == 403
    assert _upd(client, token, run["id"], status="RUNNING").json()["status"] == "RUNNING"
    assert _upd(client, token, run["id"], status="PASSED").status_code == 422  # step not passed
    r = _upd(client, token, run["id"], status="PASSED", steps=[{"stepId": step, "status": "PASSED", "durationMs": 900,
                                                                "locator": {"strategy": "RESOURCE_ID"}}]).json()
    assert r["status"] == "PASSED" and r["ended_at"] and r["steps"][0]["status"] == "PASSED"
    assert _upd(client, token, run["id"], status="FAILED").status_code == 409
    assert client.get(f"/api/replays/{run['id']}").json()["status"] == "PASSED"
    assert client.get(f"/api/sessions/{sid}/replays").json()[0]["id"] == run["id"]


def test_old_agent_rejecting_command_fails_run(client, token):
    sid = _recorded(client, token)
    run = client.post(f"/api/sessions/{sid}/replays").json()
    r = client.post(f"/api/agent/commands/{run['command_id']}/result", headers={"X-Agent-Token": token},
                    json={"status": "FAILED", "error": "Unknown command START_REPLAY"})
    assert r.status_code == 200
    r = client.get(f"/api/replays/{run['id']}").json()
    assert r["status"] == "FAILED" and r["error"]["code"] == "AGENT_COMMAND_FAILED"


def test_replay_fail_records_step_error(client, token):
    sid = _recorded(client, token, actions=("TAP", "TAP"))
    run = client.post(f"/api/sessions/{sid}/replays").json()
    _upd(client, token, run["id"], status="RUNNING")
    s1 = run["steps"][0]["stepId"]
    r = _upd(client, token, run["id"], status="FAILED", steps=[{"stepId": s1, "status": "FAILED", "error": {
        "code": "AMBIGUOUS_LOCATOR", "message": "RESOURCE_ID matched 2 elements; refusing to click."}}]).json()
    assert r["status"] == "FAILED" and r["error"]["code"] == "AMBIGUOUS_LOCATOR"
    assert [s["status"] for s in r["steps"]] == ["FAILED", "SKIPPED"]


def test_replay_rejections(client, token):
    sid = _recorded(client, token, actions=("TAP", "SWIPE"))
    r = client.post(f"/api/sessions/{sid}/replays")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_ACTION"
    assert r.json()["error"]["details"][0]["action"] == "SWIPE"
    assert not client.get(f"/api/sessions/{sid}/replays").json()
    other = _recorded(client, token, pkg="com.bank.app")
    assert client.post(f"/api/sessions/{other}/replays").json()["error"]["code"] == "APP_NOT_ALLOWED"
    unsaved = _recorded(client, token, save=False)
    assert client.post(f"/api/sessions/{unsaved}/replays").json()["error"]["code"] == "SESSION_NOT_SAVED"
    ok = _recorded(client, token)
    _hb(client, token, devices=[])
    t = client.get(f"/api/sessions/{ok}/replay-target").json()
    assert not t["compatible"] and t["error"]["code"] == "DEVICE_NOT_CONNECTED"
    demo = client.post("/api/demo/sessions").json()["id"]
    assert client.post(f"/api/sessions/{demo}/replays").json()["error"]["code"] == "DEMO_SESSION_NOT_REPLAYABLE"


def test_replay_timeout_reconcile(client, token):
    sid = _recorded(client, token)
    run = client.post(f"/api/sessions/{sid}/replays").json()
    client.portal.call(reconcile, datetime.now(timezone.utc) + timedelta(seconds=400))
    r = client.get(f"/api/replays/{run['id']}").json()
    assert r["status"] == "FAILED" and r["error"]["code"] in ("REPLAY_TIMEOUT", "AGENT_DISCONNECTED")
    assert r["steps"][0]["status"] == "SKIPPED"
    client.portal.call(db.agents.update_one, {"id": AGENT}, {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}})
