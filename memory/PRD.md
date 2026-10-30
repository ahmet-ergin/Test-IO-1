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

## Iteration 2 (2026-10-26) — Phase 1 hardening for real-device validation
- Companion + new non-sensitive sample app (`android-companion/sample-app`) build as debug APKs (Gradle 8.7/AGP 8.2.2); setup screen shows enabled/connected/events; companion-side masking of keyword/OTP fields; SERVICE_CONNECTED event
- Agent: verified on real JDK 11 (class v55); `--diagnose [--watch N]`; restricted getevent handled (no root); unsupported capabilities reported per session
- Provenance: session `environment` REAL_DEVICE / EMULATOR / SIMULATED_ADB / DEMO / null (fail-closed)
- Docs: LOCAL_VALIDATION (Mac), REAL_DEVICE_ACCEPTANCE, ACCEPTANCE_RESULTS (NOT RUN), CAPABILITIES, TEST_REPORT
- Real-device acceptance still NOT RUN

## Iteration 3 (2026-10-26) — Replay MVP (TAP via Appium 2)
- User choices: refuse non-TAP sessions before starting; stop at first failure (rest SKIPPED); noReset; Appium URL from agent config (default 127.0.0.1:4723)
- Backend: `replays` collection + `replay_service.py`; START_REPLAY via the existing command queue; endpoints replay-target / POST+GET replays / GET replay / agent status; atomic per-device lock (unique sparse `active_lock`); replay and recording exclude each other; run fails on agent command failure, agent disconnect or 180 s timeout; allowlist com.amts.sampleapp
- Agent: `replay/AppiumClient.java` (java.net.http W3C) + `replay/ReplayRunner.java` (RESOURCE_ID→UIAUTOMATOR→XPATH, ambiguous = fail, session delete in finally); new config keys appium.url, replay.find.timeout.ms, appium.session.timeout.ms, replay.allowed.packages
- UI: Replay button (Recorded Steps header + Sessions rows) with confirm dialog, /replays/:runId progress page, Replays history tab; TR/EN
- Tests: backend 36 isolated + 7 read-only external; Java 28 (7 new ReplayRunner tests with a fake Appium HTTP server); iteration_5 passed
- Physical-device replay via the AMTS UI: NOT YET VERIFIED (user to run docs/setup/REPLAY_MVP.md)

## Iteration 4 (2026-10-26) — Code Generator (Java + Appium 2 + Gauge)
- User choices: integrate into the existing framework (no new project/driver), alternatives in comments, unsupported steps generated but marked (throw), Turkish spec steps, configurable framework integration, secrets as test-data keys, preview + edit + validation, ZIP
- Backend: `services/codegen/` (config, planner, render, validate, service, javautil) + `api/codegen_routes.py` (/codegen/sessions, defaults, plan, generate, validate, zip); `_step_out` now includes `action` (schema updated in backend/schemas and shared/contracts)
- Validation: Gauge 1:1 matching, collision check, path↔package check, javac against `backend/codegen_lib` jars (java-client 9.5.0, selenium 4.34.0, gauge-java 0.11.1) with stubs for framework classes; VERIFIED only if javac passes for the selected Java version
- Frontend: /code-generator (Faz 1 menu), ConfigPanel, PlanReview, CodePreview (editable), ValidationPanel, ZIP download; config in localStorage `amts.codegen.config.v1`
- Tests: backend isolated 43 passed (7 codegen) + external 20 codegen + 7 replay; iterations 6 & 7 passed
- Docs: docs/CODEGEN.md

## Iteration 5 (2026-10-27) — Cucumber + POM profile (configurable, fictional defaults)
- User cannot share company code, so every framework name, annotation, element type, locator/action template and method verb is configurable; defaults are com.example.*; config stays in the browser (amts.codegen.pom.config.v1)
- Backend: services/codegen/pom_{config,planner,render,validate}.py + /api/codegen/pom/{defaults,plan,generate,validate,zip}; validate.py refactored (compile_java/path_errors), Gauge output unchanged; cucumber-java 7.20.1 + apiguardian added to backend/codegen_lib
- Outputs: Turkish .feature, Step Definition, Page Interface, Android Page with // <amts:members> markers; unsupported steps throw; secrets via key template
- Validation: structure, feature_match, step_collisions, java_syntax (javac with stubs), framework_compile always NOT_VERIFIED, best status STRUCTURE_VERIFIED
- Frontend: profile select (Gauge / Cucumber+POM), PomConfigPanel, copy-file / copy-members buttons
- Tests: backend 49 isolated + 46 external passed; frontend iteration_8 (crash on profile switch fixed by the tester; copy-members on readme fixed; defaults race guarded)

## Iteration 6 (2026-10-30) — Built-in "MobilDeniz - Cucumber POM" profile
- Built-in profiles defined in backend code (GENERIC, MOBILDENIZ) via GET /api/codegen/pom/profiles; customizations, profile choice and user profiles stored only in the browser (user choice); JSON export/import of user profiles
- Fixed double quoting: central javautil.fill_template_value (once-quoted, no repeated id=/xpath= prefix); findByExtraArgs (timeout = 2 default in MobilDeniz); unverifiedLocatorStrategies warning
- Cucumber 4 regex step texts (stepTextStyle REGEX) and step-text method names (stepMethodNaming STEP_TEXT); cucumber-java 4.8.1 jar for validation
- SCROLL with empty template -> MANUAL status (MANUEL UYARLAMA GEREKLİ), no parameterless swipe calls
- existingClassNames -> class_collisions WARN + plan alert
- Tests: backend 52 isolated + 53 external; iteration_9 frontend 100%

## Iteration 7 (2026-10-30) — Phase 2: sensitive data, conflict control, profile fixes
- AmtsSecureData helper (env → -D → clear error) or CUSTOM provider; PIN/OTP/şifre heuristics; sensitive_data check; report_safe masks literals in ZIP report and /pom/validate response
- Existing Cucumber steps reused only on exact unique match (REUSED); ambiguous → warning + FAIL; existing page methods matched by interface+signature (reuse / …Amts rename / overload); existing classes delivered as .amts-members.txt only; class_collisions FAIL when full .java sent for an existing class
- Profile management fixes: unique names, profileType/version on export/import, storage error toasts, builtins load failure handling
- Tests: backend 59 isolated + 72 external + Java 28; iterations 10–12 (frontend 100% in iteration 11)
- WAITING for user approval before the next phase

## Not yet done / backlog
- P0: Real-device acceptance test on user's Mac (docs/setup/LOCAL_VALIDATION.md); build companion APK
- P0: User runs physical-device replay acceptance (REPLAY_MVP.md)
- P1: User integrates generated code into the real framework and reports actual driver/helper signatures
- P1: Scroll steps with a target element (swipeUpUntilElementAppears(IMobileElement, int)) for the MobilDeniz profile
- P1: Phase 2 Locator Engine (on-device validation, scoring) — only after approval
- P2: Phase 3 AI, Phase 4 Code generator, Phase 5 Jira/Zephyr, iOS; TypeScript migration; Postgres adapter if required
