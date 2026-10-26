import uuid
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError
from core.db import db, NO_ID
from core.errors import AppError, AGENT_NOT_CONNECTED
from core.config import REPLAY_ALLOWED_PACKAGES, REPLAY_TIMEOUT_S
from models.domain import ReplayStatus as R, ACTIVE_STATES, REPLAY_ACTIVE, REPLAY_SUPPORTED_ACTIONS
from services import sessions_service as ss
from services.agent_service import connected_agent, queue_command
from services.audit import audit

LOCATOR_ORDER = ["RESOURCE_ID", "UIAUTOMATOR", "XPATH"]
STEP_RESULT_STATUSES = {"PASSED", "FAILED", "SKIPPED"}
MAX_ERR = 500


class TargetError(Exception):
    def __init__(self, code, message, status=409, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details


def replay_locators(step: dict) -> list:
    by = {loc["strategy"]: loc["value"] for loc in reversed(step.get("locators") or []) if loc.get("value")}
    return [{"strategy": s, "value": by[s]} for s in LOCATOR_ORDER if s in by]


def _full_activity(package: str, activity: str) -> str:
    return package + activity if activity.startswith(".") else activity


async def _app_activity(session: dict, steps: list):
    ev = await db.events.find_one({"eventId": steps[0]["event_id"]}, NO_ID) if steps else None
    act = (ev or {}).get("activity")
    if not act and ev and ev.get("screenId"):
        act = ((await db.screens.find_one({"id": ev["screenId"]}, NO_ID)) or {}).get("activity")
    if not act:
        return None
    act = _full_activity(session["package_name"], act)
    return act if act.startswith(session["package_name"] + ".") else None


async def _check_session(session: dict, steps: list):
    if session.get("demo"):
        raise TargetError("DEMO_SESSION_NOT_REPLAYABLE", "DEMO sessions are synthetic and cannot be replayed.")
    if session["status"] in [x.value for x in ACTIVE_STATES]:
        raise TargetError("SESSION_ACTIVE", "Stop the recording before replaying it.")
    if not session.get("saved"):
        raise TargetError("SESSION_NOT_SAVED", "Only saved recording sessions can be replayed.")
    if session.get("package_name") not in REPLAY_ALLOWED_PACKAGES:
        raise TargetError("APP_NOT_ALLOWED", f"Replay is restricted to {', '.join(sorted(REPLAY_ALLOWED_PACKAGES))} "
                          f"in this MVP (session app: {session.get('package_name') or 'unknown'}).", 422)
    if not steps:
        raise TargetError("NO_STEPS", "The session has no steps to replay.", 422)
    unsupported = [{"stepId": s["id"], "order": i + 1, "action": s["action"]}
                   for i, s in enumerate(steps) if s["action"] not in REPLAY_SUPPORTED_ACTIONS]
    if unsupported:
        names = ", ".join(f"#{u['order']} {u['action']}" for u in unsupported)
        raise TargetError("UNSUPPORTED_ACTION", f"Replay supports only TAP in this MVP. Unsupported steps: {names}. "
                          "Nothing was executed.", 422, unsupported)
    missing = [i + 1 for i, s in enumerate(steps) if not replay_locators(s)]
    if missing:
        raise TargetError("NO_REPLAYABLE_LOCATOR", f"Steps {missing} have no RESOURCE_ID, UIAUTOMATOR or XPATH "
                          "locator (coordinate replay is disabled).", 422)


async def _check_device(session: dict):
    agent = await connected_agent()
    if not agent:
        raise TargetError(*AGENT_NOT_CONNECTED, status=503)
    serial = (session.get("device") or {}).get("serial")
    dev = await db.devices.find_one({"agent_id": agent["id"], "serial": serial}, NO_ID)
    if not dev or not dev.get("online"):
        raise TargetError("DEVICE_NOT_CONNECTED", f"Recorded device {serial} is not connected to the agent.")
    if dev.get("state") != "device":
        raise TargetError("DEVICE_NOT_READY", f"Device state is '{dev.get('state')}'. Authorize USB debugging.")
    if await ss.active_session_for_device(serial):
        raise TargetError("RECORDING_ACTIVE", "A recording is active on this device; replay is blocked.")
    if await active_replay_for_device(serial):
        raise TargetError("REPLAY_ALREADY_RUNNING", "Another replay is already queued or running on this device.")
    return agent, dev


async def resolve_target(session_id: str) -> dict:
    session = await ss.get_session(session_id)
    steps = await db.steps.find({"session_id": session_id, "removed": False}, NO_ID).sort("order", 1).to_list(1000)
    out = {"sessionId": session_id, "compatible": False, "error": None, "appPackage": session.get("package_name"),
           "appActivity": None, "stepCount": len(steps),
           "device": {k: (session.get("device") or {}).get(k) for k in ("serial", "model", "manufacturer")}}
    try:
        await _check_session(session, steps)
        out["appActivity"] = await _app_activity(session, steps)
        if not out["appActivity"]:
            raise TargetError("ACTIVITY_UNKNOWN", "Launch activity of the recorded app could not be determined.", 422)
        agent, _ = await _check_device(session)
    except TargetError as e:
        out["error"] = {"code": e.code, "message": e.message, "details": e.details, "status": e.status}
        return out
    out.update(compatible=True, agentId=agent["id"], _session=session, _steps=steps)
    return out


async def active_replay_for_device(serial: str):
    return await db.replays.find_one({"device.serial": serial, "status": {"$in": [x.value for x in REPLAY_ACTIVE]}},
                                     NO_ID)


async def start_replay(session_id: str) -> dict:
    t = await resolve_target(session_id)
    if not t["compatible"]:
        e = t["error"]
        raise AppError(e["code"], e["message"], e["status"], e["details"])
    session, steps = t["_session"], t["_steps"]
    run_id, ts = str(uuid.uuid4()), ss.now_iso()
    run = {"id": run_id, "session_id": session_id, "session_name": session.get("name"), "agent_id": t["agentId"],
           "device": t["device"], "app_package": t["appPackage"], "app_activity": t["appActivity"],
           "status": R.QUEUED.value, "error": None, "created_at": ts, "started_at": None, "ended_at": None,
           "steps": [{"stepId": s["id"], "order": i + 1, "name": s.get("name"), "action": s["action"],
                      "locators": replay_locators(s), "status": "PENDING", "error": None, "locator": None,
                      "attempts": [], "durationMs": None} for i, s in enumerate(steps)]}
    payload = {"runId": run_id, "deviceSerial": t["device"]["serial"], "appPackage": run["app_package"],
               "appActivity": run["app_activity"],
               "steps": [{"stepId": s["stepId"], "order": s["order"], "action": s["action"], "locators": s["locators"]}
                         for s in run["steps"]]}
    try:
        await db.replays.insert_one({**run, "active_lock": t["device"]["serial"]})
    except DuplicateKeyError:
        raise AppError("REPLAY_ALREADY_RUNNING", "Another replay is already queued or running on this device.", 409)
    cmd = await queue_command(t["agentId"], "START_REPLAY", session_id, payload)
    await db.replays.update_one({"id": run_id}, {"$set": {"command_id": cmd["id"]}})
    await audit("REPLAY_QUEUED", "replay", run_id, {"sessionId": session_id, "device": t["device"]["serial"]})
    return await get_run(run_id)


async def get_run(run_id: str) -> dict:
    r = await db.replays.find_one({"id": run_id}, {"_id": 0, "active_lock": 0})
    if not r:
        raise AppError("REPLAY_NOT_FOUND", "Replay run not found.", 404)
    return r


def _err(e):
    if not e:
        return None
    return {"code": str(e.get("code") or "ERROR")[:64], "message": str(e.get("message") or "")[:MAX_ERR]}


async def apply_agent_update(run_id: str, body) -> dict:
    run = await get_run(run_id)
    if run["agent_id"] != body.agentId:
        raise AppError("REPLAY_AGENT_MISMATCH", "This replay run belongs to another agent.", 403)
    cur, target = R(run["status"]), body.status
    allowed = {R.QUEUED: {R.RUNNING, R.FAILED}, R.RUNNING: {R.PASSED, R.FAILED}}.get(cur, set())
    if target not in allowed:
        raise AppError("INVALID_REPLAY_TRANSITION", f"Cannot move replay from {cur.value} to {target.value}.", 409)
    steps = {s["stepId"]: s for s in run["steps"]}
    for u in body.steps:
        if u.stepId not in steps:
            raise AppError("UNKNOWN_STEP", f"Step {u.stepId} is not part of this run.", 422)
        if u.status not in STEP_RESULT_STATUSES:
            raise AppError("INVALID_STEP_STATUS", f"Invalid step status {u.status}.", 422)
        steps[u.stepId].update(status=u.status, error=_err(u.error), durationMs=u.durationMs,
                               locator=u.locator, attempts=u.attempts[:20])
    ordered = sorted(steps.values(), key=lambda s: s["order"])
    if target == R.PASSED and any(s["status"] != "PASSED" for s in ordered):
        raise AppError("REPLAY_INCOMPLETE", "PASSED requires every step to have passed.", 422)
    ts = ss.now_iso()
    upd = {"status": target.value, "steps": ordered}
    if target == R.RUNNING:
        upd["started_at"] = ts
    if target in (R.PASSED, R.FAILED):
        upd["ended_at"] = ts
        if target == R.FAILED:
            for s in ordered:
                if s["status"] == "PENDING":
                    s["status"] = "SKIPPED"
            upd["error"] = _err(body.error) or next((s["error"] for s in ordered if s["status"] == "FAILED"), None) \
                or {"code": "REPLAY_FAILED", "message": "Agent reported failure."}
        await audit(f"REPLAY_{target.value}", "replay", run_id, {"sessionId": run["session_id"]})
    unset = {"active_lock": ""} if target in (R.PASSED, R.FAILED) else {}
    await db.replays.update_one({"id": run_id}, {"$set": upd, **({"$unset": unset} if unset else {})})
    return await get_run(run_id)


async def fail_run(run: dict, code: str, message: str):
    steps = [{**s, "status": "SKIPPED" if s["status"] == "PENDING" else s["status"]} for s in run["steps"]]
    await db.replays.update_one({"id": run["id"], "status": run["status"]}, {"$unset": {"active_lock": ""}, "$set": {
        "status": R.FAILED.value, "ended_at": ss.now_iso(), "steps": steps, "error": {"code": code, "message": message}}})


async def reconcile_replays(now: datetime, stale_agents: list):
    active = [x.value for x in REPLAY_ACTIVE]
    for r in await db.replays.find({"agent_id": {"$in": stale_agents}, "status": {"$in": active}}, NO_ID).to_list(100):
        await fail_run(r, "AGENT_DISCONNECTED", "Local Recorder Agent stopped sending heartbeats during replay.")
    cut = (now - timedelta(seconds=REPLAY_TIMEOUT_S)).isoformat()
    for r in await db.replays.find({"status": {"$in": active}, "created_at": {"$lt": cut}}, NO_ID).to_list(100):
        await fail_run(r, "REPLAY_TIMEOUT", f"Replay did not finish within {REPLAY_TIMEOUT_S} s.")
