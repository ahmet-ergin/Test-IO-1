import hashlib
import secrets
from datetime import datetime, timezone
from core.db import db, NO_ID
from core.config import DEFAULT_SETTINGS

SETTINGS_ID = "global"


async def get_settings() -> dict:
    doc = await db.settings.find_one({"_id": SETTINGS_ID}, {"_id": 0}) or {}
    return {**DEFAULT_SETTINGS, **doc}


async def update_settings(patch: dict) -> dict:
    await db.settings.update_one({"_id": SETTINGS_ID}, {"$set": patch}, upsert=True)
    return await get_settings()


def public_settings(s: dict) -> dict:
    out = {k: v for k, v in s.items() if k != "agent_token_hash"}
    out["agent_token_configured"] = bool(s.get("agent_token_hash"))
    return out


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def rotate_agent_token() -> str:
    token = "amts_" + secrets.token_urlsafe(32)
    await update_settings({"agent_token_hash": hash_token(token),
                           "agent_token_created_at": datetime.now(timezone.utc).isoformat()})
    return token
