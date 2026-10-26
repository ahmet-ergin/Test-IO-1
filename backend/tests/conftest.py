import os
import sys
import uuid
from pathlib import Path
import pytest

os.environ["DB_NAME"] = f"amts_test_{uuid.uuid4().hex[:8]}"
os.environ["MONITOR_INTERVAL_S"] = "3600"
os.environ["ARTIFACTS_DIR"] = f"/tmp/amts_test_artifacts_{uuid.uuid4().hex[:6]}"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from server import app  # noqa: E402
from core.db import client as mongo  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
        c.portal.call(mongo.drop_database, os.environ["DB_NAME"])


@pytest.fixture(scope="session")
def token(client):
    return client.post("/api/settings/agent-token").json()["token"]


def device(serial="emulator-5554", state="device"):
    return {"serial": serial, "state": state, "model": "Pixel 7", "manufacturer": "Google",
            "androidVersion": "14", "sdkInt": 34, "connectionType": "USB",
            "companionInstalled": True, "companionEnabled": True}


def heartbeat(client, token, devices, agent_id="agent-test"):
    return client.post("/api/agent/heartbeat", headers={"X-Agent-Token": token}, json={
        "agentId": agent_id, "name": "test-mac", "version": "0.1.0", "os": "Mac OS X",
        "adb": {"available": True, "version": "35.0.1"}, "devices": devices})
