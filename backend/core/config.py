import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", str(ROOT_DIR / "artifacts")))
SCHEMA_DIR = ROOT_DIR / "schemas"

SCHEMA_VERSION = "1.0"
AGENT_TIMEOUT_S = int(os.environ.get("AGENT_TIMEOUT_S", "10"))
START_TIMEOUT_S = int(os.environ.get("START_TIMEOUT_S", "20"))
STOP_TIMEOUT_S = int(os.environ.get("STOP_TIMEOUT_S", "20"))
REPLAY_TIMEOUT_S = int(os.environ.get("REPLAY_TIMEOUT_S", "180"))
REPLAY_ALLOWED_PACKAGES = set(os.environ.get("REPLAY_ALLOWED_PACKAGES", "com.amts.sampleapp").split(","))
MONITOR_INTERVAL_S = float(os.environ.get("MONITOR_INTERVAL_S", "3"))

DEFAULT_SETTINGS = {
    "capture_interval_ms": 3000,
    "capture_screenshots": True,
    "redact_sensitive_regions": True,
    "mask_keywords": ["password", "passwd", "pin", "otp", "sms_code", "cvv", "cvc",
                      "secret", "token", "sifre", "şifre", "parola", "card_number"],
    "retention_days": 30,
    "external_ai_consent": False,
    "active_device_serial": None,
}
