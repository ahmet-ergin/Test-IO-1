import json
from functools import lru_cache
from jsonschema import Draft202012Validator, FormatChecker
from core.config import SCHEMA_DIR, SCHEMA_VERSION
from core.db import db, NO_ID
from core.errors import AppError
from services.sessions_service import get_session


@lru_cache
def session_schema() -> dict:
    return json.loads((SCHEMA_DIR / "recording-session.v1.schema.json").read_text())


@lru_cache
def session_validator():
    return Draft202012Validator(session_schema(), format_checker=FormatChecker())


@lru_cache
def event_validator():
    schema = session_schema()
    return Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/event"}, format_checker=FormatChecker())


def validate_event(ev: dict):
    errors = sorted(event_validator().iter_errors(ev), key=lambda e: e.path)
    return [f'{"/".join(map(str, e.path)) or "<root>"}: {e.message}' for e in errors]


def validate_session_document(doc: dict):
    return [f'{"/".join(map(str, e.path)) or "<root>"}: {e.message}' for e in session_validator().iter_errors(doc)]


def _screen_out(sc: dict) -> dict:
    keys = ["screenId", "screenName", "packageName", "activity", "width", "height", "orientation", "capturedAt",
            "hierarchyHash", "hierarchyRef", "screenshotRef", "screenshotStatus", "limitations"]
    return {k: sc.get(k) for k in keys if k in sc}


def _step_out(st: dict) -> dict:
    locs = st.get("locators") or []
    idx = st.get("selectedLocatorIndex")
    sel = locs[idx] if idx is not None and idx < len(locs) else None
    return {"stepId": st["id"], "order": st["order"], "eventId": st["event_id"], "name": st["name"],
            "description": st.get("description", ""), "verification": st.get("verification", False),
            "edited": st.get("edited", False), "selectedLocator": sel,
            "alternativeLocators": [c for i, c in enumerate(locs) if i != idx]}


async def build_export(session_id: str) -> dict:
    s = await get_session(session_id)
    events = await db.events.find({"sessionId": session_id}, {"_id": 0}).sort("sequence", 1).to_list(100000)
    steps = await db.steps.find({"session_id": session_id, "removed": False}, {"_id": 0}).sort("order", 1).to_list(100000)
    screens = await db.screens.find({"session_id": session_id}, {"_id": 0}).sort("capturedAt", 1).to_list(100000)
    for e in events:
        e.pop("received_at", None)
    dev = s.get("device") or {}
    doc = {
        "schemaVersion": SCHEMA_VERSION, "sessionId": s["id"], "name": s.get("name"), "platform": "ANDROID",
        "status": s["status"], "demo": bool(s.get("demo")), "createdAt": s.get("created_at"),
        "startedAt": s.get("started_at"), "endedAt": s.get("ended_at"), "durationMs": s["duration_ms"],
        "error": s.get("error"), "application": {"packageName": s.get("package_name")},
        "device": {k: dev.get(k) for k in ("serial", "model", "manufacturer", "androidVersion", "sdkInt")},
        "captureMode": s.get("capture_mode"), "limitations": s.get("limitations") or [],
        "screens": [_screen_out(x) for x in screens], "events": events,
        "steps": [_step_out(x) for i, x in enumerate(steps)],
    }
    for i, st in enumerate(doc["steps"], start=1):
        st["order"] = i
    errors = validate_session_document(doc)
    if errors:
        raise AppError("EXPORT_SCHEMA_INVALID", "Export failed schema validation.", 500, errors[:20])
    return doc
