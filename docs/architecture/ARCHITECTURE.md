# AI Mobile Test Studio — Architecture (Phase 1: Android Recorder MVP)

Status legend: **IMPLEMENTED** (built and tested in CI-like env) · **IMPLEMENTED – NOT DEVICE-VERIFIED** (built, unit/contract tested, awaiting real-device acceptance) · **PLANNED** (contract only).

## 1. Requirements analysis (summary)

| Area | Phase 1 decision |
|---|---|
| Recording | Hybrid: Kotlin AccessibilityService companion + ADB (`getevent`, `uiautomator dump`, `screencap`, `dumpsys`) correlated by a Java 11 local agent |
| Device access | Only the **local agent** touches USB/ADB. The web app never assumes USB access |
| Backend | Python FastAPI, REST + SSE. Persistence: **MongoDB** (platform-provided; PostgreSQL was the stated preference — the repository layer is small and isolated in `backend/services/*` so a Postgres adapter can replace it) |
| Frontend | React (JS + JSON-schema typed contracts; TypeScript migration is planned), Tailwind + shadcn/ui, TR (default) / EN, dark/light |
| Existing Java/Appium/Gauge framework | **Not touched.** Agent has zero dependency on it (only Jackson). Future integration via adapters (Phase 4) |
| AI / Codegen / Jira | **PLANNED** — UI pages are labeled "Planned — Not Implemented"; no fake behaviour |

## 2. Component architecture

```
┌──────────── Android test device ────────────┐        ┌──────── macOS dev machine ────────┐        ┌────── Backend (FastAPI) ──────┐
│ Banking/Test app                            │  USB   │ Recorder Agent (Java 11, Maven)   │ HTTPS  │ /api/agent/*  (X-Agent-Token) │
│ AMTS Companion (AccessibilityService)       │◄──────►│  adb/      AdbClient, parsers     │──────► │ /api/*        (UI)            │
│   └─ Log.i("AMTS_EVT", json)  (no network)  │  ADB   │  device/   DeviceDiscovery        │        │ state machine, ingestion,     │
│ getevent / uiautomator / screencap / dumpsys│        │  capture/  ScreenCapturer, XML    │        │ masking, locators, export     │
└─────────────────────────────────────────────┘        │  events/   getevent, correlator   │        │ MongoDB + artifacts/ (files)  │
                                                       │  session/  RecordingSession       │        └──────────────┬────────────────┘
                                                       │  transport/BackendClient (REST)   │                       │ REST + SSE
                                                       └───────────────────────────────────┘        ┌──────────────▼────────────────┐
                                                                                                    │ React web UI                  │
                                                                                                    └───────────────────────────────┘
```

* The agent **pulls** commands inside its 1 s heartbeat (`POST /api/agent/heartbeat` → `commands[]`). This works through NAT/firewalls and a cloud-hosted backend without exposing the Mac.
* Data leaves the device only over ADB to the local agent. The companion has **no INTERNET permission**.

## 3. Recording approaches evaluated

| Approach | Captures | Strengths | Limitations / permissions | Reliability |
|---|---|---|---|---|
| **AccessibilityService** | Click, long-click, text change, scroll, window change, node metadata (resource-id, text, desc, class, bounds, isPassword), IME window bounds | Semantic element info without coordinates guessing; works with FLAG_SECURE apps (accessibility is not blocked by FLAG_SECURE) | User must enable the service manually; apps may detect enabled services and refuse to run; Android 14 `accessibilityDataSensitive` views are hidden from non-tool services; Compose/custom views may lack ids; no raw coordinates; IME actions (Done/Next) not reported; password values not exposed (and we never log them) | High for clicks/text on standard views; medium on custom/WebView/Flutter |
| **ADB getevent** | Raw kernel touch (x, y, duration, multi-touch), hardware keys (BACK, ENTER) | Sees every physical touch incl. system UI; no app cooperation needed | No element info; needs coordinate scaling/rotation; gesture navigation back = swipe (no KEY_BACK); soft-keyboard taps must be filtered; some OEMs restrict `getevent` | High for coordinates; element mapping only via hierarchy lookup (may be stale) |
| **ADB uiautomator / screencap / dumpsys** | Full hierarchy XML, screenshot, focused activity, orientation, screen size | Ground truth snapshot for locators | 1–3 s per dump, fails during animations ("could not get idle state") and conflicts with a running UiAutomator2 (Appium) session; FLAG_SECURE ⇒ black screenshot | Good for snapshots, not for events |
| **Appium** | Inspection + driving | Familiar to the QA team | **Cannot intercept manual touches**; holds UiAutomation (blocks companion/uiautomator); heavy | Not suitable for recording; future use for locator validation/replay |
| **Hybrid (chosen)** | Accessibility events ⨝ getevent touches ⨝ hierarchy snapshots | Best of both; every event states its `captureSource` and `confidence`; unknowns are `null`/`uncertain` | Requires companion install + enable for full fidelity; degrades gracefully to ADB-only | Highest achievable without root/instrumentation |

## 4. How manual touches are captured (correlation algorithm)

1. `adb shell getevent -lt` → `GeteventParser` (slot-0 finger tracking, multi-touch flag) → `CoordinateMapper` (panel max → `wm size`, rotation from `dumpsys input`) → `TouchGesture` (TAP / LONG_PRESS ≥ 500 ms / SWIPE > 40 px).
2. `adb logcat -v raw -s AMTS_EVT:I` → `CompanionEvent` (device clock aligned via `date +%s%3N` offset).
3. `EventCorrelator` (800 ms window):
   * click/long-click ⨝ touch whose start point is inside node bounds → **HYBRID** (0.95) with coordinates + element.
   * scroll ⨝ swipe → SCROLL HYBRID; bursts of scroll events coalesced (600 ms).
   * accessibility click without touch → **ACCESSIBILITY** (0.85), coordinates `null` (never fabricated).
   * touch without accessibility event → **ADB_GETEVENT** (0.6); element resolved from the latest hierarchy snapshot *before* the touch, with limitation "may be stale"; if nothing found → `uncertain: true`, confidence 0.3.
   * text changes aggregated per field until 1.5 s idle or next action → one INPUT_TEXT; password fields → `masked: true, value: null, length`.
   * KEY_BACK → BACK; KEY_ENTER/TAB/SEARCH → KEYBOARD_ACTION (hardware only).
4. Touches inside the IME window (bounds from companion; heuristic lower 45 % when ADB-only and `mInputShown=true`) are **not** recorded as TAP; a count is reported as a session limitation.
5. Hierarchy is captured at start, after each action (700 ms debounce), on window change and every `capture_interval_ms`. Identical XML ⇒ skipped (no repeated screenshots). Structural hash (class + resource-id) change or activity change ⇒ SCREEN_CHANGE (ADB_UIAUTOMATOR, 0.9).
6. Every event references the snapshot captured **before** it (`screenId`, `hierarchyRef`, `screenshotRef`).

## 5. Android restrictions handled

* FLAG_SECURE: screenshot detected as blank → `screenshotStatus: BLOCKED_SECURE`, not uploaded, **not bypassed**.
* Accessibility blocked/undetectable views: events simply do not arrive → ADB-only fallback marks lower confidence.
* `unauthorized` / `offline` ADB states: shown in UI; recording refused (`DEVICE_NOT_READY`).
* Appium UiAutomator2 running concurrently: uiautomator dump fails → retried 3×, then logged; document: stop Appium sessions while recording.
* Root detection, certificate pinning, enterprise policies: not circumvented. If the app refuses to run with accessibility enabled, record ADB-only or use a debug build.

## 6. Cloud vs local

| Runs locally (Mac) | Runs in cloud/backend |
|---|---|
| ADB, device discovery, capture, correlation, first-pass masking & screenshot redaction | Session state machine, ingestion validation, defence-in-depth masking, locator extraction, storage, export, UI |

The hosted preview **cannot** see USB devices. Without a running agent the UI shows "Local Recorder Agent is not connected." and no device is ever invented.

## 7. API communication design

* Agent → backend: REST, token header `X-Agent-Token` (SHA-256 hash stored server-side, rotate in Settings).
  `POST /api/agent/heartbeat` (devices + ADB status; returns pending commands + capture settings) · `POST /api/agent/commands/{id}/result` · `POST /api/agent/sessions/{id}/state` · `POST /api/agent/sessions/{id}/screens` (multipart: metadata, hierarchy.xml, screenshot.png) · `POST /api/agent/sessions/{id}/events` (batch, JSON-schema validated, idempotent by eventId).
* UI → backend: REST + **SSE** `GET /api/sessions/{id}/stream` (fallback polling).
* Health monitor (3 s): agent heartbeat timeout 10 s ⇒ active sessions FAILED `AGENT_DISCONNECTED`; device missing from heartbeat ⇒ FAILED `DEVICE_DISCONNECTED`; STARTING > 20 s ⇒ FAILED; STOPPING > 20 s ⇒ COMPLETED with limitation.
* Full list: `docs/api/API.md`. Contract: `shared/contracts/recording-session.v1.schema.json`.

## 8. State machine

`IDLE → STARTING → RECORDING ⇄ PAUSED → STOPPING → COMPLETED`; any active state `→ FAILED`. Invalid transitions return `409 INVALID_STATE_TRANSITION`. Events are accepted only in RECORDING/STOPPING; the agent also drops input while paused.

## 9. Data model

* `sessions`, `events` (raw, immutable), `steps` (user-edited view: name, description, verification, order, removed, selected locator), `screens`, `artifacts` (files under `ARTIFACTS_DIR/<session>/`), `devices`, `agents`, `commands`, `settings`, `audit_logs`.
* Export = schema v1.0 document, validated before download.

## 10. Security

Local-first; no external AI calls exist; consent flag stored for Phase 3; passwords/OTP never stored in plaintext (companion → agent → backend each mask: isPassword, keyword list incl. Turkish `şifre/parola`, 4–8 digit OTP pattern); XML text of sensitive nodes replaced with `[MASKED]`; screenshot regions of sensitive nodes blacked out (configurable); token hashed; no secrets in code; retention purge + per-session deletion (cascade to files); audit log for token rotation, settings, exports, deletions, purges, agent pairing. Use synthetic test data.

## 11. Technical risks

| Risk | Mitigation |
|---|---|
| Banking app blocks accessibility services | ADB-only fallback, explicit limitation, debug build recommendation |
| `getevent` unavailable / OEM differences | Capability check; ADB-only accessibility mode still works |
| Hierarchy staleness for ADB-only taps | Snapshot-before-action + limitation + lower confidence |
| uiautomator dump slowness/conflicts | Debounced capture, retries, change detection |
| Clock skew device↔host | Offset measured at start; second-precision fallback reported |
| Logcat line limit (~4 KB) | Text clipped to 300 chars in companion |
| MongoDB vs PostgreSQL preference | Isolated data access; migration planned if required |

## 12. Implementation sequence

1. ✅ Contracts (JSON schema v1), backend state machine/ingestion/export + tests
2. ✅ Java agent: ADB parsers, discovery, capture, getevent, correlator, transport + JUnit tests
3. ✅ Simulated-ADB contract run (agent ⇄ backend, incl. disconnect) — **simulated, not a device test**
4. ✅ Kotlin companion source — **not built in this environment (no Android SDK)**
5. ✅ Web UI (Dashboard, Devices, Recorder, Sessions, Recorded Steps, Settings, Planned pages)
6. ⏳ Real-device acceptance test on your Mac — see `docs/setup/LOCAL_VALIDATION.md`
7. Phase 2+ only after explicit approval (`docs/architecture/FUTURE_CONTRACTS.md`)
