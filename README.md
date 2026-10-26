# AI Mobile Test Studio

Enterprise mobile test-automation recorder. **Phase 1 = Android Recorder MVP.** Phases 2–5 (Locator Engine, AI analysis, Java/Gauge code generation, Jira/Zephyr) are designed but **not implemented**.

## Status (honest)
| Component | Status |
|---|---|
| Backend (FastAPI, `backend/`) | Implemented · 29 pytest tests passing |
| Web UI (React, `frontend/`) | Implemented · TR (default) / EN · dark / light |
| Recorder Agent (Java 11 + Maven, `recorder-agent/`) | Implemented · 21 JUnit tests passing · end-to-end contract run against **simulated adb** passed (tap merge, masked PIN, BACK, disconnect) |
| Android companion (Kotlin, `android-companion/`) | Source implemented · **not compiled here** (no Android SDK in this environment) |
| Real-device acceptance | **Not yet performed** → `docs/setup/LOCAL_VALIDATION.md` |
| Locator Engine (advanced), AI, Code Generator, Jira/Zephyr, iOS | Planned — contracts in `docs/architecture/FUTURE_CONTRACTS.md` |

## Structure
```
backend/            FastAPI: api/ (routes) · core/ (config, db, errors) · models/ · services/ · schemas/ · tests/
frontend/           React UI: pages/ · components/ · context/ · hooks/ · i18n/ · lib/
recorder-agent/     Java 11 local agent: adb/ · device/ · capture/ · events/ · session/ · transport/ · tools/fake-adb (SIMULATED)
android-companion/  Kotlin AccessibilityService (logcat transport, no network permission)
shared/contracts/   recording-session.v1.schema.json (canonical contract, identical copy in backend/schemas, test-enforced)
docs/               architecture/ · api/ · setup/
```
Deviations from the proposed tree: `integrations/` is not created (no Phase 4/5 code yet — avoided empty implementations); the repository layer lives in `backend/services/` (MongoDB via Motor, the platform database); tests live next to each component (`backend/tests`, `recorder-agent/src/test`).

## Quick start
See `docs/setup/LOCAL_VALIDATION.md`. Architecture: `docs/architecture/ARCHITECTURE.md`. API: `docs/api/API.md`.

## Security notes
No external AI calls exist. Passwords/OTPs are masked at companion, agent and backend. Screenshots of FLAG_SECURE screens are not bypassed. Agent token is hashed server-side; `agent.properties` is git-ignored. Use test devices and synthetic data only.
