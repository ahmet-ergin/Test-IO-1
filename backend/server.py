import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS, MONITOR_INTERVAL_S, SCHEMA_VERSION
from core.db import client, ensure_indexes
from core.errors import AppError, app_error_handler
from api import agent_routes, session_routes, ui_routes, demo_routes, replay_routes, codegen_routes
from services.agent_service import reconcile
from services.export_service import session_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("amts")


async def _monitor():
    while True:
        try:
            await reconcile()
        except Exception:
            logger.exception("monitor failed")
        await asyncio.sleep(MONITOR_INTERVAL_S)


@asynccontextmanager
async def lifespan(_app):
    await ensure_indexes()
    task = asyncio.create_task(_monitor())
    yield
    task.cancel()
    client.close()


app = FastAPI(title="AI Mobile Test Studio API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)

api = APIRouter(prefix="/api")


@api.get("/health")
async def health():
    return {"status": "ok", "schemaVersion": SCHEMA_VERSION}


@api.get("/schemas/recording-session")
async def get_schema():
    return session_schema()


for r in (agent_routes.router, session_routes.router, ui_routes.router, demo_routes.router, replay_routes.router, codegen_routes.router):
    api.include_router(r)
app.include_router(api)

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])
