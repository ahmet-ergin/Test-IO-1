# Backend API (v0.1, schema 1.0)

Base: `${BACKEND_URL}/api`. Errors: `{"error": {"code", "message", "details"}}`.

## UI endpoints
| Method | Path | Notes |
|---|---|---|
| GET | /health | `{status, schemaVersion}` |
| GET | /schemas/recording-session | JSON schema v1 |
| GET | /status | agent connection, active session, stats |
| GET | /devices | `agentConnected:false` + message "Local Recorder Agent is not connected." when no heartbeat in 10 s |
| POST | /devices/refresh | 503 `AGENT_NOT_CONNECTED` if no agent |
| POST | /devices/{serial}/select | sets active device |
| POST | /sessions | `{deviceSerial, name?, packageFilter?}` → STARTING; errors `AGENT_NOT_CONNECTED`, `DEVICE_NOT_CONNECTED`, `DEVICE_NOT_READY`, `SESSION_ALREADY_ACTIVE` |
| POST | /sessions/{id}/pause · /resume · /stop | 409 `INVALID_STATE_TRANSITION` |
| GET | /sessions · /sessions/{id} | |
| PATCH | /sessions/{id} | `{name?, saved?}` (save only when not active) |
| DELETE | /sessions/{id} | Clear/delete incl. artifacts (not while active) |
| GET | /sessions/{id}/events?after=N | raw immutable event log |
| GET | /sessions/{id}/screens | snapshots |
| GET | /sessions/{id}/steps | edited steps |
| PATCH | /steps/{id} | `{name?, description?, verification?, selectedLocatorIndex?}` |
| DELETE | /steps/{id} | soft remove; raw event kept |
| POST | /sessions/{id}/steps/reorder | `{order:[stepIds]}` returns dependency warning |
| GET | /sessions/{id}/export | schema-validated JSON download |
| GET | /sessions/{id}/stream | SSE: `{session, events}` every 1 s |
| GET | /artifacts/{id} | screenshot PNG / hierarchy XML |
| GET/PUT | /settings | capture/masking/retention |
| POST | /settings/agent-token | returns token once |
| GET | /audit-logs | |
| POST | /retention/purge?include_saved=false | |
| POST | /demo/sessions | synthetic session, `demo:true`, `captureSource:"DEMO"` |

## Agent endpoints (header `X-Agent-Token`)
| Method | Path | Body |
|---|---|---|
| POST | /agent/heartbeat | `{agentId, name, version, os, javaVersion, adb:{available,version,error}, devices:[...], activeSessionId}` → `{commands, settings}` |
| POST | /agent/commands/{id}/result | `{status: DONE|FAILED, error?}` |
| POST | /agent/sessions/{id}/state | `{status: RECORDING|COMPLETED|FAILED, packageName?, limitations?, captureMode?, error?}` |
| POST | /agent/sessions/{id}/screens | multipart `metadata` (JSON), `hierarchy` (xml), `screenshot` (png) |
| POST | /agent/sessions/{id}/events | `{events:[event v1]}` → `{accepted, rejected[]}` |

Commands: `START_SESSION` (payload: deviceSerial, packageFilter, settings), `PAUSE_SESSION`, `RESUME_SESSION`, `STOP_SESSION`, `REFRESH_DEVICES`.
