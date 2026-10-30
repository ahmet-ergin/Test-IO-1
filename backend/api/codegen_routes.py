from typing import List
from urllib.parse import quote
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field
from core.db import db
from models.domain import ACTIVE_STATES
from services.audit import audit
from services.codegen.config import CodegenConfig, resolve
from services.codegen.planner import build_plan
from services.codegen import service as cg
from services.codegen.javautil import words
from services.codegen.validate import validate_files
from services.sessions_service import get_session
from services.codegen.pom_config import PomConfig, resolve_pom, builtin_profiles
from services.codegen.pom_planner import build_pom_plan
from services.codegen.pom_render import generate_files as pom_files
from services.codegen.pom_validate import validate_pom

router = APIRouter(prefix="/codegen", tags=["codegen"])


class PlanRequest(BaseModel):
    sessionId: str
    config: CodegenConfig = Field(default_factory=CodegenConfig)


class CodeFile(BaseModel):
    path: str
    content: str
    language: str = ""
    role: str = ""


class FilesRequest(BaseModel):
    sessionId: str
    config: CodegenConfig = Field(default_factory=CodegenConfig)
    files: List[CodeFile]


class PomPlanRequest(BaseModel):
    sessionId: str
    config: PomConfig = Field(default_factory=PomConfig)


class PomFilesRequest(PomPlanRequest):
    files: List[CodeFile]


@router.get("/defaults")
async def defaults():
    return CodegenConfig().model_dump()


@router.get("/sessions")
async def sessions():
    active = [s.value for s in ACTIVE_STATES]
    rows = await db.sessions.find({"status": {"$nin": active}}, {"_id": 0, "id": 1, "name": 1, "status": 1, "saved": 1, "demo": 1,
                                                                  "package_name": 1, "created_at": 1}).sort("created_at", -1).to_list(500)
    out = []
    for r in rows:
        acts = await db.steps.aggregate([{"$match": {"session_id": r["id"], "removed": False}},
                                         {"$group": {"_id": "$action", "n": {"$sum": 1}}}]).to_list(50)
        out.append({k: v for k, v in r.items() if k != "_id"} | {"actions": {a["_id"]: a["n"] for a in acts},
                                                                  "stepCount": sum(a["n"] for a in acts)})
    return out


@router.post("/plan")
async def plan(body: PlanRequest):
    return await build_plan(body.sessionId, body.config)


@router.post("/generate")
async def generate(body: PlanRequest):
    res = await cg.generate(body.sessionId, body.config)
    await audit("CODEGEN_GENERATED", "session", body.sessionId, {"status": res["validation"]["status"]})
    return res


async def _validated(body: FilesRequest):
    s = await get_session(body.sessionId)
    files = [f.model_dump() for f in body.files]
    cg.check_files(files)
    return s, files, await validate_files(files, resolve(body.config, s.get("name") or "Recorded"))


@router.post("/validate")
async def validate(body: FilesRequest):
    _, _, v = await _validated(body)
    return v


@router.post("/zip")
async def zip_export(body: FilesRequest):
    s, files, v = await _validated(body)
    data = cg.build_zip(files, v, s.get("name") or "")
    await audit("CODEGEN_ZIP_EXPORTED", "session", body.sessionId, {"status": v["status"], "files": len(files)})
    name = "amts-" + ("-".join(w.lower() for w in words(s.get("name") or "")) or "session") + "-gauge.zip"
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}",
        "X-AMTS-Validation": v["status"], "Access-Control-Expose-Headers": "X-AMTS-Validation, Content-Disposition"})


@router.get("/pom/defaults")
async def pom_defaults():
    return PomConfig().model_dump()


@router.get("/pom/profiles")
async def pom_profiles():
    return builtin_profiles()


@router.post("/pom/plan")
async def pom_plan(body: PomPlanRequest):
    return await build_pom_plan(body.sessionId, body.config)


@router.post("/pom/generate")
async def pom_generate(body: PomPlanRequest):
    plan = await build_pom_plan(body.sessionId, body.config)
    rc = PomConfig(**plan["config"])
    files = pom_files(plan, rc)
    v = await validate_pom(files, rc, plan["classes"])
    await audit("CODEGEN_GENERATED", "session", body.sessionId, {"profile": "CUCUMBER_POM", "status": v["status"]})
    return {"plan": plan, "files": files, "validation": v}


async def _pom_validated(body: PomFilesRequest):
    s = await get_session(body.sessionId)
    files = [f.model_dump() for f in body.files]
    cg.check_files(files)
    rc = resolve_pom(body.config, s.get("name") or "Recorded")
    return s, files, await validate_pom(files, rc, rc.names())


@router.post("/pom/validate")
async def pom_validate(body: PomFilesRequest):
    _, _, v = await _pom_validated(body)
    return cg.report_safe(v)


@router.post("/pom/zip")
async def pom_zip(body: PomFilesRequest):
    s, files, v = await _pom_validated(body)
    data = cg.build_zip(files, v, s.get("name") or "")
    await audit("CODEGEN_ZIP_EXPORTED", "session", body.sessionId, {"profile": "CUCUMBER_POM", "status": v["status"]})
    name = "amts-" + ("-".join(w.lower() for w in words(s.get("name") or "")) or "session") + "-cucumber-pom.zip"
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}",
        "X-AMTS-Validation": v["status"], "Access-Control-Expose-Headers": "X-AMTS-Validation, Content-Disposition"})
