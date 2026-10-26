import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("amts")


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details


async def app_error_handler(_: Request, exc: AppError):
    logger.warning("AppError %s: %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.status,
                        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})


AGENT_NOT_CONNECTED = ("AGENT_NOT_CONNECTED", "Local Recorder Agent is not connected.")
