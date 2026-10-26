import json
import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from core.db import db, NO_ID
from core.errors import AppError
from models.domain import (StartSessionRequest, UpdateSessionRequest, UpdateStepRequest, ReorderStepsRequest,
                           RecordingStatus as S, ACTIVE_STATES)
from services import sessions_service as ss
from services.agent_service import require_connected_agent, queue_command
from services.settings_service import get_settings
from services.export_service import build_export
from services.audit import audit

router = APIRouter(tags=["sessions"])


@router.post("/sessions")
async def start_session(body: StartSessionRequest):
    agent = await require_connected_agent()
    dev = await db.devices.find_one({"agent_id": agent["id"], "serial": body.deviceSerial}, {"_id": 0})
    if not dev or not dev.get("online"):
        raise AppError("DEVICE_NOT_CONNECTED", "Selected device is not connected to the agent.", 409)
    if dev.get("state") != "device":
        raise AppError("DEVICE_NOT_READY", f"Device state is '{dev.get('state')}'. Authorize USB debugging.", 409)
    if await ss.active_session_for_device(body.deviceSerial):
        raise AppError("SESSION_ALREADY_ACTIVE", "A recording is already active on this device.", 409)
    settings = await get_settings()
    sid = str(uuid.uuid4())
    ts = ss.now_iso()
    session = {
        "id": sid, "name": body.name or f"Recording {ts[:19].replace('T', ' ')}", "status": S.STARTING.value,
        "demo": False, "saved": False, "agent_id": agent["id"], "created_at": ts, "started_at": None,
        "ended_at": None, "paused_at": None, "paused_total_ms": 0, "event_count": 0, "screen_count": 0,
        "package_filter": body.packageFilter, "package_name": None, "latest_screen_id": None, "error": None,
        "limitations": [], "capture_mode": None,
        "device": {k: dev.get(k) for k in ("serial", "model", "manufacturer", "androidVersion", "sdkInt",
                                           "connectionType")},
        "state_history": [{"from": S.IDLE.value, "to": S.STARTING.value, "at": ts, "actor": "ui-user"}],
    }
    await db.sessions.insert_one(dict(session))
    await queue_command(agent["id"], "START_SESSION", sid, {
        "deviceSerial": body.deviceSerial, "packageFilter": body.packageFilter,
        "settings": {k: settings[k] for k in ("capture_interval_ms", "capture_screenshots",
                                              "redact_sensitive_regions", "mask_keywords")}})
    return await ss.get_session(sid)


async def _control(session_id: str, target: S, command: str):
    s = await ss.get_session(session_id)
    if s.get("demo"):
        raise AppError("DEMO_SESSION_READONLY", "Demo sessions cannot be controlled.", 409)
    updated = await ss.transition(session_id, target, "ui-user")
    await queue_command(s["agent_id"], command, session_id)
    return updated


@router.post("/sessions/{session_id}/pause")
async def pause(session_id: str):
    return await _control(session_id, S.PAUSED, "PAUSE_SESSION")


@router.post("/sessions/{session_id}/resume")
async def resume(session_id: str):
    return await _control(session_id, S.RECORDING, "RESUME_SESSION")


@router.post("/sessions/{session_id}/stop")
async def stop(session_id: str):
    return await _control(session_id, S.STOPPING, "STOP_SESSION")


@router.get("/sessions")
async def list_sessions(limit: int = 200):
    items = await db.sessions.find({}, {"_id": 0, "state_history": 0}).sort("created_at", -1).to_list(limit)
    for s in items:
        s["duration_ms"] = ss.duration_ms(s)
    return items


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    s = await ss.get_session(session_id)
    if s.get("latest_screen_id"):
        s["latest_screen"] = await db.screens.find_one({"id": s["latest_screen_id"]}, {"_id": 0})
    return s


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: UpdateSessionRequest):
    s = await ss.get_session(session_id)
    patch = body.model_dump(exclude_none=True)
    if patch.get("saved") and s["status"] in [x.value for x in ACTIVE_STATES]:
        raise AppError("SESSION_ACTIVE", "Stop the recording before saving.", 409)
    if patch:
        await db.sessions.update_one({"id": session_id}, {"$set": patch})
    if patch.get("saved"):
        await audit("SESSION_SAVED", target=session_id)
    return await ss.get_session(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    s = await ss.get_session(session_id)
    if s["status"] in [x.value for x in ACTIVE_STATES]:
        raise AppError("SESSION_ACTIVE", "Stop the recording before clearing or deleting it.", 409)
    await ss.delete_session_cascade(session_id)
    await audit("SESSION_DELETED", target=session_id, details={"name": s.get("name"), "demo": s.get("demo")})
    return {"deleted": session_id}


@router.get("/sessions/{session_id}/events")
async def list_events(session_id: str, after: int = 0):
    await ss.get_session(session_id)
    return await db.events.find({"sessionId": session_id, "sequence": {"$gt": after}},
                                {"_id": 0, "received_at": 0}).sort("sequence", 1).to_list(100000)


@router.get("/sessions/{session_id}/screens")
async def list_screens(session_id: str):
    return await db.screens.find({"session_id": session_id}, {"_id": 0}).sort("capturedAt", 1).to_list(100000)


@router.get("/sessions/{session_id}/steps")
async def list_steps(session_id: str, include_removed: bool = False):
    q = {"session_id": session_id} if include_removed else {"session_id": session_id, "removed": False}
    return await db.steps.find(q, {"_id": 0}).sort("order", 1).to_list(100000)


@router.patch("/steps/{step_id}")
async def update_step(step_id: str, body: UpdateStepRequest):
    step = await db.steps.find_one({"id": step_id}, {"_id": 0})
    if not step:
        raise AppError("STEP_NOT_FOUND", "Step not found.", 404)
    patch = body.model_dump(exclude_none=True)
    idx = patch.get("selectedLocatorIndex")
    if idx is not None and not (0 <= idx < len(step.get("locators") or [])):
        raise AppError("INVALID_LOCATOR_INDEX", "Locator index out of range.", 422)
    await db.steps.update_one({"id": step_id}, {"$set": {**patch, "edited": True}})
    return await db.steps.find_one({"id": step_id}, {"_id": 0})


@router.delete("/steps/{step_id}")
async def remove_step(step_id: str):
    r = await db.steps.update_one({"id": step_id}, {"$set": {"removed": True, "edited": True}})
    if not r.matched_count:
        raise AppError("STEP_NOT_FOUND", "Step not found.", 404)
    await audit("STEP_REMOVED", target=step_id)
    return {"removed": step_id, "note": "Original event is preserved in the raw event log."}


@router.post("/sessions/{session_id}/steps/reorder")
async def reorder_steps(session_id: str, body: ReorderStepsRequest):
    current = await db.steps.find({"session_id": session_id, "removed": False}, {"_id": 0}).to_list(100000)
    if sorted(body.order) != sorted(s["id"] for s in current):
        raise AppError("INVALID_ORDER", "Order must contain exactly the session's active step IDs.", 422)
    for i, sid in enumerate(body.order, start=1):
        await db.steps.update_one({"id": sid}, {"$set": {"order": i}})
    return {"ok": True, "warning": "Reordering may break execution dependencies between screens."}


@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str):
    doc = await build_export(session_id)
    await audit("SESSION_EXPORTED", target=session_id)
    return JSONResponse(doc, headers={"Content-Disposition": f'attachment; filename="recording-{session_id}.json"'})


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    doc = await db.artifacts.find_one({"id": artifact_id}, {"_id": 0})
    if not doc or not Path(doc["path"]).exists():
        raise AppError("ARTIFACT_NOT_FOUND", "Artifact not found or deleted by retention policy.", 404)
    return FileResponse(doc["path"], media_type=doc["content_type"])


@router.get("/sessions/{session_id}/stream")
async def stream(session_id: str, request: Request, after: int = 0):
    await ss.get_session(session_id)

    async def gen():
        last_seq, last_status = after, None
        while not await request.is_disconnected():
            s = await ss.get_session(session_id)
            evs = await db.events.find({"sessionId": session_id, "sequence": {"$gt": last_seq}},
                                       {"_id": 0, "received_at": 0}).sort("sequence", 1).to_list(500)
            if evs:
                last_seq = evs[-1]["sequence"]
            s.pop("state_history", None)
            yield f"data: {json.dumps({'session': s, 'events': evs})}\n\n"
            if s["status"] in (S.COMPLETED.value, S.FAILED.value) and last_status == s["status"] and not evs:
                break
            last_status = s["status"]
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
