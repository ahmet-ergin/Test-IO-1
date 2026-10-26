import uuid
from datetime import datetime, timezone, timedelta
from conftest import device, heartbeat
from services.agent_service import reconcile
from services.export_service import validate_session_document, validate_event


def _ev(sid, seq, action="TAP", **kw):
    return {"eventId": str(uuid.uuid4()), "sessionId": sid, "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(), "action": action, "deviceId": "emulator-5554",
            "packageName": "com.example.app", "captureSource": "HYBRID", "confidence": 0.95, "uncertain": False,
            "limitations": [], **kw}


def test_no_agent_message(client):
    r = client.get("/api/devices").json()
    assert r["agentConnected"] is False and r["message"] == "Local Recorder Agent is not connected."
    r = client.post("/api/sessions", json={"deviceSerial": "x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "AGENT_NOT_CONNECTED"


def test_agent_auth_required(client, token):
    r = client.post("/api/agent/heartbeat", headers={"X-Agent-Token": "bad"}, json={})
    assert r.status_code == 401


def test_full_recording_flow(client, token):
    assert heartbeat(client, token, [device()]).status_code == 200
    d = client.get("/api/devices").json()
    assert d["agentConnected"] and d["devices"][0]["model"] == "Pixel 7"
    s = client.post("/api/sessions", json={"deviceSerial": "emulator-5554"}).json()
    sid = s["id"]
    assert s["status"] == "STARTING"
    cmds = heartbeat(client, token, [device()]).json()["commands"]
    assert cmds[0]["type"] == "START_SESSION" and cmds[0]["session_id"] == sid
    # pause invalid while STARTING
    assert client.post(f"/api/sessions/{sid}/pause").status_code == 409
    h = {"X-Agent-Token": token}
    r = client.post(f"/api/agent/sessions/{sid}/state", headers=h,
                    json={"status": "RECORDING", "packageName": "com.example.app", "limitations": ["x"]})
    assert r.json()["status"] == "RECORDING"
    xml = '<hierarchy><node resource-id="com.example.app:id/pin" password="true" text="1234"/></hierarchy>'
    scr = client.post(f"/api/agent/sessions/{sid}/screens", headers=h,
                      data={"metadata": '{"packageName":"com.example.app","activity":".LoginActivity","width":1080}'},
                      files={"hierarchy": ("h.xml", xml, "application/xml")}).json()
    assert "1234" not in client.get(f"/api/artifacts/{scr['hierarchyRef']}").text
    evs = [_ev(sid, 1, "SCREEN_CHANGE", screenId=scr["screenId"], hierarchyRef=scr["hierarchyRef"]),
           _ev(sid, 2, "INPUT_TEXT", hierarchyRef=scr["hierarchyRef"],
               element={"resourceId": "com.example.app:id/pin", "password": True},
               inputValue={"masked": False, "value": "1234", "length": 4}),
           _ev(sid, 3, "TAP", coordinates={"x": 5, "y": 6})]
    bad = _ev(sid, 4, "FLY")
    r = client.post(f"/api/agent/sessions/{sid}/events", headers=h, json={"events": evs + [bad]}).json()
    assert r["accepted"] == 3 and len(r["rejected"]) == 1
    # duplicates ignored
    assert client.post(f"/api/agent/sessions/{sid}/events", headers=h, json={"events": evs}).json()["accepted"] == 0
    stored = client.get(f"/api/sessions/{sid}/events").json()
    assert [e["sequence"] for e in stored] == [1, 2, 3]
    assert stored[1]["inputValue"]["masked"] is True and stored[1]["inputValue"]["value"] is None
    steps = client.get(f"/api/sessions/{sid}/steps").json()
    assert len(steps) == 2  # SCREEN_CHANGE is not a step
    assert client.post(f"/api/sessions/{sid}/pause").json()["status"] == "PAUSED"
    assert client.post(f"/api/agent/sessions/{sid}/events", headers=h,
                       json={"events": [_ev(sid, 9)]}).status_code == 409
    assert client.post(f"/api/sessions/{sid}/pause").status_code == 409
    assert client.post(f"/api/sessions/{sid}/resume").json()["status"] == "RECORDING"
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"] == "STOPPING"
    assert client.patch(f"/api/sessions/{sid}", json={"saved": True}).status_code == 409
    r = client.post(f"/api/agent/sessions/{sid}/state", headers=h, json={"status": "COMPLETED"}).json()
    assert r["status"] == "COMPLETED" and r["ended_at"]
    # step editing keeps raw events untouched
    st = steps[1]
    client.patch(f"/api/steps/{st['id']}", json={"name": "Tap login", "verification": True})
    client.delete(f"/api/steps/{steps[0]['id']}")
    assert len(client.get(f"/api/sessions/{sid}/events").json()) == 3
    assert len(client.get(f"/api/sessions/{sid}/steps").json()) == 1
    assert client.patch(f"/api/sessions/{sid}", json={"saved": True}).json()["saved"] is True
    exp = client.get(f"/api/sessions/{sid}/export").json()
    assert validate_session_document(exp) == []
    assert exp["schemaVersion"] == "1.0" and exp["steps"][0]["name"] == "Tap login"
    assert exp["steps"][0]["verification"] is True


def test_device_disconnect_fails_session(client, token):
    heartbeat(client, token, [device("dev-2")])
    sid = client.post("/api/sessions", json={"deviceSerial": "dev-2"}).json()["id"]
    client.post(f"/api/agent/sessions/{sid}/state", headers={"X-Agent-Token": token}, json={"status": "RECORDING"})
    heartbeat(client, token, [])
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["status"] == "FAILED" and s["error"]["code"] == "DEVICE_DISCONNECTED"
    assert client.get("/api/devices").json()["devices"][0]["online"] is False


def test_unauthorized_device_cannot_record(client, token):
    heartbeat(client, token, [device("dev-3", "unauthorized")])
    r = client.post("/api/sessions", json={"deviceSerial": "dev-3"})
    assert r.json()["error"]["code"] == "DEVICE_NOT_READY"


def test_agent_timeout_fails_session(client, token):
    heartbeat(client, token, [device("dev-4")], agent_id="agent-2")
    sid = client.post("/api/sessions", json={"deviceSerial": "dev-4"}).json()["id"]
    client.post(f"/api/agent/sessions/{sid}/state", headers={"X-Agent-Token": token}, json={"status": "RECORDING"})
    client.portal.call(reconcile, datetime.now(timezone.utc) + timedelta(seconds=60))
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["status"] == "FAILED" and s["error"]["code"] == "AGENT_DISCONNECTED"


def test_demo_session_is_labeled_and_valid(client):
    s = client.post("/api/demo/sessions").json()
    assert s["demo"] is True and s["device"]["model"].startswith("DEMO")
    exp = client.get(f"/api/sessions/{s['id']}/export").json()
    assert exp["demo"] is True and all(e["captureSource"] == "DEMO" for e in exp["events"])
    assert client.post(f"/api/sessions/{s['id']}/stop").status_code == 409
    assert client.delete(f"/api/sessions/{s['id']}").status_code == 200


def test_event_schema_rejects_bad_confidence():
    ev = _ev("s", 1)
    ev["confidence"] = 1.5
    assert validate_event(ev)


def test_shared_contract_matches_backend_schema():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    shared = root / "shared/contracts/recording-session.v1.schema.json"
    assert shared.read_text() == (root / "backend/schemas/recording-session.v1.schema.json").read_text()
