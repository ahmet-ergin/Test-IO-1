# AI Mobile Test Studio — PRD

## Original problem statement (summary)
Enterprise AI-powered mobile test automation platform (Recorder, Locator Engine, AI understanding, framework-aware Java/Gauge code generator, Jira/Zephyr). Implement ONLY Phase 1: Android Recorder MVP — real, testable, no fabricated devices/events; demo clearly labeled; TR default + EN; dark/light; security (masking, local-first, no external AI uploads, retention, audit).

## User choices
- Hybrid recording: Kotlin AccessibilityService companion + ADB (hierarchy, screenshots, device info, transitions); uncertain actions marked, never invented
- Local Recorder Agent: Java 11 + Maven, standalone, independent of existing Appium/Gauge framework; REST (+SSE to UI), versioned JSON contracts
- Backend Python/FastAPI (MongoDB used — platform DB; Postgres preference noted)

## Architecture
backend/ (FastAPI: api, core, models, services, schemas, tests) · frontend/ (React) · recorder-agent/ (Java) · android-companion/ (Kotlin) · shared/contracts/ (schema v1) · docs/

## Implemented (2026-10-26)
- Backend: agent pairing token (hashed), heartbeat+command pull, device registry, session state machine (409 on invalid), events ingestion w/ JSON-schema validation + idempotency + masking, screen/artifact upload (XML masked), basic locator extraction w/ uniqueness from snapshot, editable steps separate from raw events, reorder/remove/verification, export validated JSON, SSE stream, monitor (agent timeout, device disconnect, start/stop timeouts), settings, retention purge, audit log, DEMO sessions. 29 + 18 tests pass.
- Java agent: ADB discovery, getevent parser/mapper, companion logcat parser, correlator (HYBRID/ACCESSIBILITY/ADB_GETEVENT), screen capture w/ change detection, FLAG_SECURE detection, redaction, IME filtering, transport. 21 JUnit tests pass. Simulated-adb e2e contract run passed.
- Kotlin companion source (not compiled here — no Android SDK).
- UI: Dashboard, Devices, Recorder (live SSE feed, screenshot overlay), Sessions, Recorded Steps (inspector drawer, raw log tab), Settings, Planned pages.

## Not yet done / backlog
- P0: Real-device acceptance test on user's Mac (docs/setup/LOCAL_VALIDATION.md); build companion APK
- P1: Phase 2 Locator Engine (on-device validation, scoring) — only after approval
- P2: Phase 3 AI, Phase 4 Code generator, Phase 5 Jira/Zephyr, iOS; TypeScript migration; Postgres adapter if required
