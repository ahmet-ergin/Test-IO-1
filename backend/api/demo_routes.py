"""Demo mode: synthetic sessions, always flagged demo=true and captureSource=DEMO. Never mixed with real devices."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from core.db import db
from services import sessions_service as ss
from services.artifacts import store_artifact
from services.audit import audit

router = APIRouter(prefix="/demo", tags=["demo"])

PKG = "com.example.demobank"
DEMO_XML = f"""<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">
<node index="0" class="android.widget.FrameLayout" package="{PKG}" bounds="[0,0][1080,2340]">
<node index="0" class="android.widget.Button" resource-id="{PKG}:id/transferButton" text="Transfer" content-desc="" clickable="true" password="false" bounds="[100,200][350,260]"/>
<node index="1" class="android.widget.Button" resource-id="{PKG}:id/eftButton" text="EFT" content-desc="eft_option" clickable="true" password="false" bounds="[100,300][350,360]"/>
<node index="2" class="android.widget.EditText" resource-id="{PKG}:id/ibanInput" text="" hint="IBAN" clickable="true" password="false" bounds="[60,420][1020,500]"/>
<node index="3" class="android.widget.EditText" resource-id="{PKG}:id/pinInput" text="" hint="PIN" clickable="true" password="true" bounds="[60,540][1020,620]"/>
<node index="4" class="android.widget.Button" resource-id="{PKG}:id/continueButton" text="Continue" clickable="true" password="false" bounds="[60,2100][1020,2200]"/>
</node></hierarchy>"""

STEPS = [
    ("SCREEN_CHANGE", None, None),
    ("TAP", {"resourceId": f"{PKG}:id/transferButton", "text": "Transfer", "className": "android.widget.Button",
             "bounds": [100, 200, 350, 260]}, None),
    ("TAP", {"resourceId": f"{PKG}:id/eftButton", "text": "EFT", "contentDesc": "eft_option",
             "className": "android.widget.Button", "bounds": [100, 300, 350, 360]}, None),
    ("INPUT_TEXT", {"resourceId": f"{PKG}:id/ibanInput", "hint": "IBAN", "className": "android.widget.EditText",
                    "bounds": [60, 420, 1020, 500]}, "TR000000000000000000000000"),
    ("INPUT_TEXT", {"resourceId": f"{PKG}:id/pinInput", "hint": "PIN", "className": "android.widget.EditText",
                    "password": True, "bounds": [60, 540, 1020, 620]}, None),
    ("TAP", {"resourceId": f"{PKG}:id/continueButton", "text": "Continue", "className": "android.widget.Button",
             "bounds": [60, 2100, 1020, 2200]}, None),
]


@router.post("/sessions")
async def create_demo_session():
    sid = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    xml_ref = await store_artifact(sid, "HIERARCHY_XML", DEMO_XML.encode(), "xml", "application/xml")
    screen_id = str(uuid.uuid4())
    await db.screens.insert_one({"id": screen_id, "screenId": screen_id, "session_id": sid, "screenName": "DEMO TransferScreen",
                                 "packageName": PKG, "activity": f"{PKG}.TransferActivity", "width": 1080,
                                 "height": 2340, "orientation": 0, "capturedAt": t0.isoformat(),
                                 "hierarchyRef": xml_ref, "screenshotRef": None, "screenshotStatus": "DISABLED",
                                 "limitations": ["DEMO data — synthetic, not captured from a device."]})
    await db.sessions.insert_one({
        "id": sid, "name": "DEMO — EFT transfer (synthetic)", "status": "COMPLETED", "demo": True, "environment": "DEMO", "saved": False,
        "agent_id": None, "created_at": t0.isoformat(), "started_at": t0.isoformat(),
        "ended_at": (t0 + timedelta(seconds=len(STEPS) * 2)).isoformat(), "paused_at": None, "paused_total_ms": 0,
        "event_count": len(STEPS), "screen_count": 1, "package_name": PKG, "latest_screen_id": screen_id,
        "error": None, "capture_mode": {"demo": True},
        "limitations": ["DEMO session: synthetic data, no device was used."],
        "device": {"serial": "DEMO-0000", "model": "DEMO Device", "manufacturer": "DEMO", "androidVersion": "14",
                   "sdkInt": 34, "connectionType": None},
        "state_history": [{"from": "IDLE", "to": "COMPLETED", "at": t0.isoformat(), "actor": "demo"}]})
    for i, (action, element, value) in enumerate(STEPS, start=1):
        ev = {"eventId": str(uuid.uuid4()), "sessionId": sid, "sequence": i,
              "timestamp": (t0 + timedelta(seconds=i * 2)).isoformat(), "action": action, "deviceId": "DEMO-0000",
              "packageName": PKG, "activity": f"{PKG}.TransferActivity", "screenId": screen_id,
              "hierarchyRef": xml_ref, "screenshotRef": None,
              "element": {**element, "resolvedFrom": "DEMO"} if element else None,
              "coordinates": None, "captureSource": "DEMO", "confidence": 1.0, "uncertain": False,
              "limitations": ["DEMO event"]}
        if action == "INPUT_TEXT":
            ev["inputValue"] = ({"masked": False, "value": value, "length": len(value)} if value
                                else {"masked": True, "value": None, "length": 4, "reason": "SENSITIVE_FIELD"})
        await db.events.insert_one(dict(ev))
        await ss.create_step_for_event(ev)
    await audit("DEMO_SESSION_CREATED", target=sid)
    return await ss.get_session(sid)
