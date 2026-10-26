from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RecordingStatus(str, Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    RECORDING = "RECORDING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ACTIVE_STATES = {RecordingStatus.STARTING, RecordingStatus.RECORDING,
                 RecordingStatus.PAUSED, RecordingStatus.STOPPING}
STEP_EXCLUDED_ACTIONS = {"SCREEN_CHANGE"}


class StartSessionRequest(BaseModel):
    deviceSerial: str
    name: Optional[str] = None
    packageFilter: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    saved: Optional[bool] = None


class UpdateStepRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    verification: Optional[bool] = None
    selectedLocatorIndex: Optional[int] = None


class ReorderStepsRequest(BaseModel):
    order: List[str]


class SettingsUpdate(BaseModel):
    capture_interval_ms: Optional[int] = Field(None, ge=500, le=60000)
    capture_screenshots: Optional[bool] = None
    redact_sensitive_regions: Optional[bool] = None
    mask_keywords: Optional[List[str]] = None
    retention_days: Optional[int] = Field(None, ge=1, le=3650)
    external_ai_consent: Optional[bool] = None


class AgentDevice(BaseModel):
    serial: str
    state: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    androidVersion: Optional[str] = None
    sdkInt: Optional[int] = None
    connectionType: Optional[str] = None
    companionInstalled: Optional[bool] = None
    companionEnabled: Optional[bool] = None
    screenWidth: Optional[int] = None
    screenHeight: Optional[int] = None


class AdbInfo(BaseModel):
    available: bool
    simulated: Optional[bool] = None
    version: Optional[str] = None
    error: Optional[str] = None


class HeartbeatRequest(BaseModel):
    agentId: str
    name: str
    version: str
    os: Optional[str] = None
    javaVersion: Optional[str] = None
    adb: AdbInfo
    devices: List[AgentDevice] = []
    activeSessionId: Optional[str] = None


class CommandResult(BaseModel):
    status: str
    error: Optional[str] = None


class AgentSessionState(BaseModel):
    status: RecordingStatus
    error: Optional[str] = None
    packageName: Optional[str] = None
    limitations: List[str] = []
    captureMode: Optional[dict] = None


class EventBatch(BaseModel):
    events: List[dict]
