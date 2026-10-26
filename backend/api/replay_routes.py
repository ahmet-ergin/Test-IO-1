from fastapi import APIRouter
from core.db import db
from services import replay_service as rs
from services import sessions_service as ss

router = APIRouter(tags=["replay"])


@router.get("/sessions/{session_id}/replay-target")
async def replay_target(session_id: str):
    t = await rs.resolve_target(session_id)
    return {k: v for k, v in t.items() if not k.startswith("_")}


@router.post("/sessions/{session_id}/replays")
async def start_replay(session_id: str):
    return await rs.start_replay(session_id)


@router.get("/sessions/{session_id}/replays")
async def list_replays(session_id: str, limit: int = 20):
    await ss.get_session(session_id)
    runs = await db.replays.find({"session_id": session_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [{k: v for k, v in r.items() if k != "_id"} for r in runs]


@router.get("/replays/{run_id}")
async def get_replay(run_id: str):
    return await rs.get_run(run_id)
