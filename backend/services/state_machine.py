from models.domain import RecordingStatus as S
from core.errors import AppError

TRANSITIONS = {
    S.IDLE: {S.STARTING},
    S.STARTING: {S.RECORDING, S.STOPPING, S.FAILED},
    S.RECORDING: {S.PAUSED, S.STOPPING, S.FAILED},
    S.PAUSED: {S.RECORDING, S.STOPPING, S.FAILED},
    S.STOPPING: {S.COMPLETED, S.FAILED},
    S.COMPLETED: set(),
    S.FAILED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return S(target) in TRANSITIONS[S(current)]


def assert_transition(current: str, target: str):
    if not can_transition(current, target):
        raise AppError("INVALID_STATE_TRANSITION",
                       f"Cannot transition recording from {current} to {target}.", 409,
                       {"from": current, "to": target})
