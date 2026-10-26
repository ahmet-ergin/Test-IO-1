# AI Mobile Test Studio

Enterprise mobile test-automation recorder. **Phase 1 = Android Recorder MVP.** Phases 2–5 (Locator Engine, AI analysis, Java/Gauge code generation, Jira/Zephyr) are designed but **not implemented**. The existing Java/Appium/Gauge framework is not used or modified.

## Status
| Component | Status |
|---|---|
| Backend (FastAPI, `backend/`) | Implemented · 30 self-contained tests pass + 25 environment-dependent tests (see `docs/TEST_REPORT.md`) |
| Web UI (React, `frontend/`) | Implemented · TR (default) / EN · dark / light |
| Recorder Agent (Java 11 + Maven, `recorder-agent/`) | Implemented · built and tested on **real JDK 11** (21 JUnit tests) · `--diagnose` device checker · simulated-adb end-to-end passes |
| Android companion (Kotlin, `android-companion/app`) | **APK builds** (debug) · setup screen with enabled/connected status · **not yet installed on a device** |
| Sample test app (`android-companion/sample-app`) | **APK builds** · non-sensitive screens for acceptance testing |
| Real-device acceptance | **NOT RUN** → `docs/setup/REAL_DEVICE_ACCEPTANCE.md` |

## Docs
* Mac setup and run: `docs/setup/LOCAL_VALIDATION.md`
* Real-device acceptance script and results template: `docs/setup/REAL_DEVICE_ACCEPTANCE.md`, `docs/setup/ACCEPTANCE_RESULTS.md`
* Supported / unsupported capture: `docs/setup/CAPABILITIES.md`
* Build and test report: `docs/TEST_REPORT.md`
* Architecture: `docs/architecture/ARCHITECTURE.md` · Future contracts: `docs/architecture/FUTURE_CONTRACTS.md` · API: `docs/api/API.md`

## Structure
```
backend/            FastAPI: api/ · core/ · models/ · services/ · schemas/ · tests/
frontend/           React UI
recorder-agent/     Java 11 agent: adb/ device/ capture/ events/ session/ transport/ Diagnostics · tools/fake-adb (SIMULATED)
android-companion/  Gradle project: app/ (AccessibilityService companion) · sample-app/ (test app) · prebuilt/ (debug APKs + SHA256SUMS)
shared/contracts/   recording-session.v1.schema.json (canonical; identical copy in backend/schemas, enforced by a test)
docs/
```
`integrations/` is intentionally absent (no Phase 4/5 code yet).

## Result provenance
Every session has `environment` set to `REAL_DEVICE`, `SIMULATED_ADB` (fake-adb contract tests) or `DEMO` (synthetic). Only `REAL_DEVICE` sessions count as device evidence.
