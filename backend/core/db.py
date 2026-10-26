from motor.motor_asyncio import AsyncIOMotorClient
from core.config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

NO_ID = {"_id": 0}


async def ensure_indexes():
    await db.sessions.create_index("id", unique=True)
    await db.events.create_index("eventId", unique=True)
    await db.events.create_index([("sessionId", 1), ("sequence", 1)])
    await db.steps.create_index([("session_id", 1), ("order", 1)])
    await db.screens.create_index("id", unique=True)
    await db.devices.create_index([("agent_id", 1), ("serial", 1)], unique=True)
    await db.commands.create_index([("agent_id", 1), ("status", 1)])
    await db.audit_logs.create_index("timestamp")
    await db.replays.create_index("id", unique=True)
    await db.replays.create_index("active_lock", unique=True, sparse=True)
    await db.replays.create_index([("device.serial", 1), ("status", 1)])
