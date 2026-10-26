import uuid
import logging
from datetime import datetime, timezone
from core.db import db

logger = logging.getLogger("amts.audit")


async def audit(action: str, actor: str = "ui-user", target: str = None, details: dict = None):
    entry = {"id": str(uuid.uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(),
             "action": action, "actor": actor, "target": target, "details": details or {}}
    await db.audit_logs.insert_one(entry)
    logger.info("AUDIT %s target=%s", action, target)
