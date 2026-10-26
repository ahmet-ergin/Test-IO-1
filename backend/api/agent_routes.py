import json
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile
from core.db import db, NO_ID
from core.errors import AppError
from models.domain import (HeartbeatRequest, CommandResult, AgentSessionState, EventBatch, ReplayStatusUpdate,
                           RecordingStatus as S)
from services.agent_service import require_agent_token, pull_commands, handle_device_changes
from services.settings_service import get_settings
from services import sessions_service as ss
from services.masking import mask_event, mask_hierarchy_xml
from services.artifacts import store_artifact
from services.export_service import validate_event
from services.audit import audit
from services import replay_service as rs

logger = logging.getLogger("amts.agent")
router = APIRouter(prefix="/agent", dependencies=[Depends(require_agent_token)], tags=["agent"])

AGENT_SETTING_KEYS = ["capture_interval_ms", "capture_screenshots", "redact_sensitive_regions", "mask_keywords"]


@router.post("/heartbeat")
async def heartbeat(body: HeartbeatRequest):
    ts = ss.now_iso()
    first = not await db.agents.find_one({"id": body.agentId})
    await db.agents.update_one({"id": body.agentId}, {"$set": {
        "id": body.agentId, "name": body.name, "version": body.version, "os": body.os,
        "java_version": body.javaVersion, "adb": body.adb.model_dump(), "last_seen": ts}}, upsert=True)
    if first:
        await audit("AGENT_PAIRED", "agent", body.agentId, {"name": body.name, "os": body.os})
    devices = [d.model_dump() for d in body.devices]
    seen = []
    for d in devices:
        seen.append(d["serial"])
        await db.devices.update_one({"agent_id": body.agentId, "serial": d["serial"]},
                                    {"$set": {**d, "agent_id": body.agentId, "online": True, "last_seen": ts}},
                                    upsert=True)
    await db.devices.update_many({"agent_id": body.agentId, "serial": {"$nin": seen}}, {"$set": {"online": False}})
    await handle_device_changes(body.agentId, devices)
    settings = await get_settings()
    return {"serverTime": ts, "commands": await pull_commands(body.agentId),
            "settings": {k: settings[k] for k in AGENT_SETTING_KEYS}}


@router.post("/commands/{command_id}/result")
async def command_result(command_id: str, body: CommandResult):
    r = await db.commands.update_one({"id": command_id}, {"$set": {"status": body.status, "error": body.error,
                                                                   "completed_at": ss.now_iso()}})
    if not r.matched_count:
        raise AppError("COMMAND_NOT_FOUND", "Command not found.", 404)
    if body.status == "FAILED":
        run = await db.replays.find_one({"command_id": command_id, "status": {"$in": ["QUEUED", "RUNNING"]}}, NO_ID)
        if run:
            await rs.fail_run(run, "AGENT_COMMAND_FAILED", f"Agent could not execute replay: {(body.error or '')[:300]}")
    return {"ok": True}


@router.post("/sessions/{session_id}/state")
async def session_state(session_id: str, body: AgentSessionState):
    if body.status not in (S.RECORDING, S.COMPLETED, S.FAILED):
        raise AppError("INVALID_AGENT_STATE", "Agent may only report RECORDING, COMPLETED or FAILED.", 422)
    s = await ss.get_session(session_id)
    if body.status == S.RECORDING and s["status"] != S.STARTING.value:
        raise AppError("INVALID_STATE_TRANSITION", f"Cannot confirm RECORDING from {s['status']}.", 409)
    extra = {}
    if body.packageName:
        extra["package_name"] = body.packageName
    if body.limitations:
        extra["limitations"] = sorted(set((s.get("limitations") or []) + body.limitations))
    if body.captureMode is not None:
        extra["capture_mode"] = body.captureMode
    if body.status == S.FAILED:
        extra["error"] = {"code": "AGENT_REPORTED_FAILURE", "message": body.error or "Agent reported failure."}
    return await ss.transition(session_id, body.status, "agent", **extra)


@router.post("/sessions/{session_id}/screens")
async def upload_screen(session_id: str, metadata: str = Form(...), hierarchy: Optional[UploadFile] = File(None),
                        screenshot: Optional[UploadFile] = File(None)):
    s = await ss.get_session(session_id)
    if s["status"] not in (S.STARTING.value, S.RECORDING.value, S.STOPPING.value):
        raise AppError("SESSION_NOT_RECORDING", f"Session is {s['status']}; screen rejected.", 409)
    meta = json.loads(metadata)
    settings = await get_settings()
    screen = {"id": str(uuid.uuid4()), "session_id": session_id, "hierarchyRef": None, "screenshotRef": None,
              "limitations": meta.get("limitations") or []}
    screen["screenId"] = screen["id"]
    for k in ("packageName", "activity", "width", "height", "orientation", "capturedAt", "hierarchyHash",
              "screenshotStatus"):
        screen[k] = meta.get(k)
    screen["capturedAt"] = screen["capturedAt"] or ss.now_iso()
    act = screen.get("activity")
    screen["screenName"] = act.split(".")[-1] if act else (screen.get("packageName") or "UnknownScreen")
    if hierarchy is not None:
        xml = mask_hierarchy_xml((await hierarchy.read()).decode("utf-8", errors="replace"), settings["mask_keywords"])
        screen["hierarchyRef"] = await store_artifact(session_id, "HIERARCHY_XML", xml.encode(), "xml", "application/xml")
    if screenshot is not None:
        screen["screenshotRef"] = await store_artifact(session_id, "SCREENSHOT", await screenshot.read(), "png", "image/png")
    elif not screen.get("screenshotStatus"):
        screen["screenshotStatus"] = "DISABLED"
    await db.screens.insert_one(dict(screen))
    upd = {"latest_screen_id": screen["id"]}
    if screen.get("packageName"):
        upd["package_name"] = screen["packageName"]
    await db.sessions.update_one({"id": session_id}, {"$set": upd, "$inc": {"screen_count": 1}})
    return {"screenId": screen["id"], "hierarchyRef": screen["hierarchyRef"], "screenshotRef": screen["screenshotRef"]}


@router.post("/sessions/{session_id}/events")
async def ingest_events(session_id: str, body: EventBatch):
    s = await ss.get_session(session_id)
    if s["status"] not in (S.RECORDING.value, S.STOPPING.value):
        raise AppError("SESSION_NOT_RECORDING", f"Session is {s['status']}; events rejected.", 409,
                       {"rejected": len(body.events)})
    settings = await get_settings()
    accepted, rejected = 0, []
    for ev in body.events:
        ev["sessionId"] = session_id
        errs = validate_event(ev)
        if errs:
            rejected.append({"eventId": ev.get("eventId"), "errors": errs})
            continue
        if await db.events.find_one({"eventId": ev["eventId"]}):
            continue
        ev = mask_event(ev, settings["mask_keywords"])
        ev["received_at"] = ss.now_iso()
        await db.events.insert_one(dict(ev))
        await ss.create_step_for_event(ev)
        accepted += 1
    if accepted:
        await db.sessions.update_one({"id": session_id}, {"$inc": {"event_count": accepted}})
    if rejected:
        logger.warning("Rejected %d events for %s: %s", len(rejected), session_id, rejected[:3])
    return {"accepted": accepted, "rejected": rejected}


@router.post("/replays/{run_id}/status")
async def replay_status(run_id: str, body: ReplayStatusUpdate):
    return await rs.apply_agent_update(run_id, body)
