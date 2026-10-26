import hashlib
import shutil
import uuid
from pathlib import Path
from core.config import ARTIFACTS_DIR
from core.db import db


async def store_artifact(session_id: str, kind: str, data: bytes, ext: str, content_type: str) -> str:
    art_id = str(uuid.uuid4())
    folder = ARTIFACTS_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{art_id}.{ext}"
    path.write_bytes(data)
    await db.artifacts.insert_one({"id": art_id, "session_id": session_id, "kind": kind, "path": str(path),
                                   "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                                   "content_type": content_type})
    return art_id


async def read_artifact_text(art_id: str):
    if not art_id:
        return None
    doc = await db.artifacts.find_one({"id": art_id})
    if not doc or not Path(doc["path"]).exists():
        return None
    return Path(doc["path"]).read_text(encoding="utf-8", errors="replace")


async def delete_session_artifacts(session_id: str):
    await db.artifacts.delete_many({"session_id": session_id})
    shutil.rmtree(ARTIFACTS_DIR / session_id, ignore_errors=True)
