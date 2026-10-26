# Replay MVP (Phase 1 add-on) — Android TAP replay via Appium 2

Status: implemented; **physical-device replay through the AMTS UI is NOT yet verified** (pending the user's Mac run).

## Scope / restrictions
- Only saved, non-DEMO, COMPLETED sessions of `com.amts.sampleapp` (backend `REPLAY_ALLOWED_PACKAGES`, agent `replay.allowed.packages`).
- Only `TAP` steps. A session that has any other action is refused **before anything runs** (`UNSUPPORTED_ACTION`, lists the steps).
- Locator order: `RESOURCE_ID` → `UIAUTOMATOR` → `XPATH`. Coordinates are never used.
- A locator that matches more than one element fails the step with `AMBIGUOUS_LOCATOR`, and nothing is clicked.
- The run stops at the first failed step; the steps after it are marked `SKIPPED`.
- The app is not reset (`noReset=true`). Appium just launches the recorded activity (`com.amts.sampleapp.HomeActivity`).
- Replay and recording exclude each other on a device: the backend and the agent both block one while the other is active.

## Flow
1. UI → `POST /api/sessions/{id}/replays`. The backend validates the target, creates a run (`QUEUED`) and queues `START_REPLAY` for the connected agent.
2. The agent's heartbeat pulls the command. `AgentApp.handle()` → `ReplayRunner.run()` (on the existing single-thread executor).
3. Agent → `POST /api/agent/replays/{runId}/status` `RUNNING`, then: create the Appium session → find elements → click → `DELETE` the session (always runs, in `finally`).
4. Agent → status `PASSED`/`FAILED`, with a result for each step. The UI polls `GET /api/replays/{runId}` every 1 s.
5. Safety nets: the run fails if the agent rejects the command (`AGENT_COMMAND_FAILED`, e.g. an old agent build), if heartbeats stop (`AGENT_DISCONNECTED`), or after `REPLAY_TIMEOUT_S` (default 180 s, `REPLAY_TIMEOUT`).

## API contracts
| Method | Path | Notes |
|---|---|---|
| GET | `/api/sessions/{id}/replay-target` | `{compatible, error{code,message,details,status}, device{serial,model,manufacturer}, appPackage, appActivity, stepCount}` |
| POST | `/api/sessions/{id}/replays` | 200 run doc; 409 (`DEVICE_NOT_CONNECTED`, `RECORDING_ACTIVE`, `REPLAY_ALREADY_RUNNING`, `SESSION_NOT_SAVED`, `DEMO_SESSION_NOT_REPLAYABLE`), 422 (`UNSUPPORTED_ACTION`, `APP_NOT_ALLOWED`, `NO_REPLAYABLE_LOCATOR`, `ACTIVITY_UNKNOWN`), 503 `AGENT_NOT_CONNECTED` |
| GET | `/api/sessions/{id}/replays` | newest first |
| GET | `/api/replays/{runId}` | run doc |
| POST | `/api/agent/replays/{runId}/status` | agent token. Body `{agentId, status: RUNNING\|PASSED\|FAILED, error?, steps:[{stepId,status: PASSED\|FAILED\|SKIPPED,error?,locator?,attempts[],durationMs}]}`. Allowed transitions: QUEUED→RUNNING/FAILED, RUNNING→PASSED/FAILED. 403 if the run belongs to another agent. A PASSED report is rejected (422) unless every step passed. |

The run doc (Mongo `replays`) contains: `id, session_id, agent_id, device, app_package, app_activity, status, error, created_at, started_at, ended_at, command_id`, and `steps[{stepId, order, name, action, locators, status, error, locator, attempts, durationMs}]`.

`START_REPLAY` payload: `{runId, deviceSerial, appPackage, appActivity, steps:[{stepId, order, action, locators:[{strategy,value}]}]}`.

## Agent configuration (`agent.properties`; `AMTS_*` env vars override)
```
appium.url=http://127.0.0.1:4723          # AMTS_APPIUM_URL
replay.find.timeout.ms=10000              # per step, polling every 500 ms
appium.session.timeout.ms=120000          # POST /session (UiAutomator2 startup)
replay.allowed.packages=com.amts.sampleapp
```
The agent sends plain W3C WebDriver calls through `java.net.http` (`replay/AppiumClient.java`). There is no Appium Java Client and no change to the global Java/Node/Appium installations. Other commands time out after 30 s, and the connection timeout is 5 s. Logs show only run IDs, step numbers, locator strategies and error codes. They never include tokens, locator values or element text.

## Physical-device acceptance (to be run by the user)
1. `appium` (Appium 2 with UiAutomator2 already installed) listening on 127.0.0.1:4723.
2. Rebuild and restart the agent: `cd recorder-agent && mvn -q package && java -jar target/recorder-agent.jar agent.properties`.
3. Sample App installed on the Xiaomi phone, which is connected by USB and shown as online in AMTS Devices.
4. AMTS → Recorded Steps → "Xiaomi - Sample App - İlk Kayıt" → **Replay** → check the device and app in the dialog → **Start Replay**.
5. Expected: the run page goes QUEUED → RUNNING → **PASSED**, step #1 shows `RESOURCE_ID · com.amts.sampleapp:id/transferButton`, and the TRANSFER button is tapped on the phone.
