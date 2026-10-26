import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Header
from core.db import db, NO_ID
from core.errors import AppError, AGENT_NOT_CONNECTED
from core.config import AGENT_TIMEOUT_S, START_TIMEOUT_S, STOP_TIMEOUT_S
from models.domain import RecordingStatus as S, ACTIVE_STATES
from services.settings_service import get_settings, hash_token
from services import sessions_service as ss

logger = logging.getLogger("amts.agent")


async def require_agent_token(x_agent_token: Optional[str] = Header(None)):
    settings = await get_settings()
    if not settings.get("agent_token_hash"):
        raise AppError("AGENT_TOKEN_NOT_CONFIGURED", "No agent pairing token generated. Create one in Settings.", 401)
    if not x_agent_token or hash_token(x_agent_token) != settings["agent_token_hash"]:
        raise AppError("AGENT_UNAUTHORIZED", "Invalid agent token.", 401)
    return True


def _now():
    return datetime.now(timezone.utc)


async def connected_agent():
    cutoff = (_now() - timedelta(seconds=AGENT_TIMEOUT_S)).isoformat()
    return await db.agents.find_one({"last_seen": {"$gte": cutoff}}, {"_id": 0}, sort=[("last_seen", -1)])


async def require_connected_agent():
    agent = await connected_agent()
    if not agent:
        raise AppError(*AGENT_NOT_CONNECTED, status=503)
    return agent


async def queue_command(agent_id: str, ctype: str, session_id: str = None, payload: dict = None):
    cmd = {"id": str(uuid.uuid4()), "agent_id": agent_id, "type": ctype, "session_id": session_id,
           "payload": payload or {}, "status": "PENDING", "created_at": _now().isoformat()}
    await db.commands.insert_one(dict(cmd))
    cmd.pop("_id", None)
    return cmd


async def pull_commands(agent_id: str):
    cmds = await db.commands.find({"agent_id": agent_id, "status": "PENDING"}, {"_id": 0}).sort("created_at", 1).to_list(50)
    if cmds:
        await db.commands.update_many({"id": {"$in": [c["id"] for c in cmds]}},
                                      {"$set": {"status": "DELIVERED", "delivered_at": _now().isoformat()}})
    return cmds


async def handle_device_changes(agent_id: str, devices: list):
    """Fail active sessions whose device vanished or is no longer in 'device' state."""
    online = {d["serial"] for d in devices if d["state"] == "device"}
    active = await db.sessions.find({"agent_id": agent_id, "status": {"$in": [x.value for x in ACTIVE_STATES]}},
                                    NO_ID).to_list(100)
    for s in active:
        if s["device"]["serial"] not in online:
            logger.warning("Device %s disconnected during session %s", s["device"]["serial"], s["id"])
            await ss.transition(s["id"], S.FAILED, "system", error={
                "code": "DEVICE_DISCONNECTED", "message": "Android device disconnected during recording."})


async def reconcile(now: datetime = None):
    """Periodic health check: agent timeouts, stuck STARTING/STOPPING sessions."""
    now = now or _now()
    cutoff = (now - timedelta(seconds=AGENT_TIMEOUT_S)).isoformat()
    stale_agents = [a["id"] for a in await db.agents.find({"last_seen": {"$lt": cutoff}}, {"_id": 0}).to_list(100)]
    if stale_agents:
        await db.devices.update_many({"agent_id": {"$in": stale_agents}}, {"$set": {"online": False}})
        for s in await db.sessions.find({"agent_id": {"$in": stale_agents},
                                         "status": {"$in": [x.value for x in ACTIVE_STATES]}}, {"_id": 0}).to_list(100):
            await ss.transition(s["id"], S.FAILED, "system", error={
                "code": "AGENT_DISCONNECTED", "message": "Local Recorder Agent stopped sending heartbeats."})
    from services.replay_service import reconcile_replays
    await reconcile_replays(now, stale_agents)
    start_cut = (now - timedelta(seconds=START_TIMEOUT_S)).isoformat()
    for s in await db.sessions.find({"status": S.STARTING.value, "created_at": {"$lt": start_cut}}, {"_id": 0}).to_list(100):
        await ss.transition(s["id"], S.FAILED, "system", error={
            "code": "AGENT_START_TIMEOUT", "message": "Agent did not confirm recording start in time."})
    stop_cut = (now - timedelta(seconds=STOP_TIMEOUT_S)).isoformat()
    for s in await db.sessions.find({"status": S.STOPPING.value, "stop_requested_at": {"$lt": stop_cut}},
                                    NO_ID).to_list(100):
        await ss.transition(s["id"], S.COMPLETED, "system", limitations=(s.get("limitations") or []) + [
            "Agent did not confirm stop; trailing events may be missing."])
