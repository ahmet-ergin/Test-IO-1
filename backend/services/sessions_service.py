import uuid
from datetime import datetime, timezone
from core.db import db, NO_ID
from core.errors import AppError
from models.domain import RecordingStatus as S, ACTIVE_STATES, STEP_EXCLUDED_ACTIONS
from services.state_machine import assert_transition
from services.locators import extract_locators
from services.artifacts import read_artifact_text, delete_session_artifacts


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ms(iso):
    return datetime.fromisoformat(iso).timestamp() * 1000 if iso else None


def duration_ms(s: dict) -> int:
    if not s.get("started_at"):
        return 0
    end = _ms(s.get("ended_at")) or datetime.now(timezone.utc).timestamp() * 1000
    paused = s.get("paused_total_ms", 0)
    if s.get("paused_at"):
        paused += end - _ms(s["paused_at"])
    return max(0, int(end - _ms(s["started_at"]) - paused))


async def get_session(session_id: str) -> dict:
    s = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise AppError("SESSION_NOT_FOUND", "Recording session not found.", 404)
    s["duration_ms"] = duration_ms(s)
    return s


async def transition(session_id: str, target: S, actor: str, **extra) -> dict:
    s = await get_session(session_id)
    assert_transition(s["status"], target.value)
    ts = now_iso()
    update = {"status": target.value, **extra}
    if target == S.RECORDING and s["status"] == S.STARTING.value:
        update["started_at"] = ts
    if target == S.PAUSED:
        update["paused_at"] = ts
    if target == S.RECORDING and s["status"] == S.PAUSED.value and s.get("paused_at"):
        update["paused_total_ms"] = s.get("paused_total_ms", 0) + int(_ms(ts) - _ms(s["paused_at"]))
        update["paused_at"] = None
    if target == S.STOPPING:
        update["stop_requested_at"] = ts
    if target in (S.COMPLETED, S.FAILED):
        update["ended_at"] = ts
        if s.get("paused_at"):
            update["paused_total_ms"] = s.get("paused_total_ms", 0) + int(_ms(ts) - _ms(s["paused_at"]))
            update["paused_at"] = None
        if not s.get("started_at"):
            update["started_at"] = ts
    await db.sessions.update_one({"id": session_id}, {
        "$set": update,
        "$push": {"state_history": {"from": s["status"], "to": target.value, "at": ts, "actor": actor}}})
    return await get_session(session_id)


async def active_session_for_device(serial: str):
    return await db.sessions.find_one({"device.serial": serial, "status": {"$in": [x.value for x in ACTIVE_STATES]}}, {"_id": 0})


def step_label(ev: dict) -> str:
    el = ev.get("element") or {}
    label = el.get("text") or el.get("contentDesc") or (el.get("resourceId") or "").split("/")[-1] or None
    if not label and ev.get("coordinates"):
        label = f'({ev["coordinates"]["x"]}, {ev["coordinates"]["y"]})'
    return f'{ev["action"]} {label}' if label else ev["action"]


async def create_step_for_event(ev: dict):
    if ev["action"] in STEP_EXCLUDED_ACTIONS:
        return
    xml = None
    if ev.get("hierarchyRef"):
        xml = await read_artifact_text(ev["hierarchyRef"])
    locators = extract_locators(ev.get("element"), ev.get("coordinates"), xml)
    last = await db.steps.find_one({"session_id": ev["sessionId"]}, sort=[("order", -1)])
    await db.steps.insert_one({
        "id": str(uuid.uuid4()), "session_id": ev["sessionId"], "event_id": ev["eventId"],
        "order": (last["order"] + 1) if last else 1, "name": step_label(ev), "description": "",
        "verification": False, "removed": False, "action": ev["action"],
        "locators": locators, "selectedLocatorIndex": 0 if locators else None,
        "edited": False, "created_at": now_iso()})


async def delete_session_cascade(session_id: str):
    await db.events.delete_many({"sessionId": session_id})
    for coll in (db.steps, db.screens, db.commands):
        await coll.delete_many({"session_id": session_id})
    await delete_session_artifacts(session_id)
    await db.sessions.delete_one({"id": session_id})
