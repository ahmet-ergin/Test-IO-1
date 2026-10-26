from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from core.db import db, NO_ID
from core.errors import AppError
from models.domain import SettingsUpdate, ACTIVE_STATES
from services.agent_service import connected_agent, require_connected_agent, queue_command
from services.settings_service import get_settings, update_settings, public_settings, rotate_agent_token
from services import sessions_service as ss
from services.audit import audit

router = APIRouter(tags=["ui"])


def _agent_out(a):
    if not a:
        return None
    return {"id": a["id"], "name": a.get("name"), "version": a.get("version"), "os": a.get("os"),
            "javaVersion": a.get("java_version"), "adb": a.get("adb"), "lastSeen": a.get("last_seen")}


@router.get("/status")
async def status():
    agent = await connected_agent()
    settings = await get_settings()
    active = await db.sessions.find_one({"status": {"$in": [x.value for x in ACTIVE_STATES]}, "demo": False},
                                        {"_id": 0, "state_history": 0}, sort=[("created_at", -1)])
    if active:
        active["duration_ms"] = ss.duration_ms(active)
    online = await db.devices.count_documents({"agent_id": agent["id"], "online": True}) if agent else 0
    return {"agentConnected": bool(agent), "agent": _agent_out(agent), "onlineDevices": online,
            "activeDeviceSerial": settings.get("active_device_serial"), "activeSession": active,
            "agentTokenConfigured": bool(settings.get("agent_token_hash")),
            "stats": {"sessions": await db.sessions.count_documents({}),
                      "savedSessions": await db.sessions.count_documents({"saved": True}),
                      "events": await db.events.count_documents({})}}


@router.get("/devices")
async def devices():
    agent = await connected_agent()
    if not agent:
        last = await db.agents.find_one({}, {"_id": 0}, sort=[("last_seen", -1)])
        return {"agentConnected": False, "message": "Local Recorder Agent is not connected.",
                "lastAgent": _agent_out(last), "adb": None, "devices": []}
    devs = await db.devices.find({"agent_id": agent["id"]}, {"_id": 0, "agent_id": 0}).sort("serial", 1).to_list(100)
    for d in devs:
        d["recording"] = bool(await ss.active_session_for_device(d["serial"]))
    return {"agentConnected": True, "agent": _agent_out(agent), "adb": agent.get("adb"), "devices": devs}


@router.post("/devices/refresh")
async def refresh_devices():
    agent = await require_connected_agent()
    return await queue_command(agent["id"], "REFRESH_DEVICES")


@router.post("/devices/{serial}/select")
async def select_device(serial: str):
    agent = await require_connected_agent()
    if not await db.devices.find_one({"agent_id": agent["id"], "serial": serial, "online": True}):
        raise AppError("DEVICE_NOT_CONNECTED", "Device is not connected.", 404)
    await update_settings({"active_device_serial": serial})
    return {"activeDeviceSerial": serial}


@router.get("/settings")
async def read_settings():
    return public_settings(await get_settings())


@router.put("/settings")
async def write_settings(body: SettingsUpdate):
    patch = body.model_dump(exclude_none=True)
    if "mask_keywords" in patch:
        patch["mask_keywords"] = sorted({k.strip().lower() for k in patch["mask_keywords"] if k.strip()})
    s = await update_settings(patch)
    await audit("SETTINGS_UPDATED", details={"keys": list(patch)})
    return public_settings(s)


@router.post("/settings/agent-token")
async def new_agent_token():
    token = await rotate_agent_token()
    await audit("AGENT_TOKEN_ROTATED")
    return {"token": token, "note": "Shown once. Store it in recorder-agent/agent.properties (never commit it)."}


@router.get("/audit-logs")
async def audit_logs(limit: int = 100):
    return await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)


@router.post("/retention/purge")
async def purge(include_saved: bool = False):
    settings = await get_settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings["retention_days"])).isoformat()
    q = {"created_at": {"$lt": cutoff}, "status": {"$nin": [x.value for x in ACTIVE_STATES]}}
    if not include_saved:
        q["saved"] = {"$ne": True}
    ids = [s["id"] for s in await db.sessions.find(q, {"id": 1}).to_list(100000)]
    for sid in ids:
        await ss.delete_session_cascade(sid)
    await audit("RETENTION_PURGE", details={"deleted": len(ids), "cutoff": cutoff, "includeSaved": include_saved})
    return {"deleted": len(ids), "cutoff": cutoff}
