# Build & test report (Phase 1, iteration 2)

All results below were produced in the Linux **aarch64** build container. **No physical Android device or emulator was available**, so no row here is a device result.

## Builds
| Artifact | Command | Result |
|---|---|---|
| Recorder Agent jar | `JAVA_HOME=<Temurin 11.0.32> mvn -B clean package` | **BUILD OK**, 21/21 JUnit tests pass, class file major version **55 (Java 11)** |
| Recorder Agent jar | same with JDK 17.0.21 | BUILD OK (compiles with `--release 11`) |
| Companion APK `com.amts.companion` | `./gradlew assembleDebug` (Gradle 8.7, AGP 8.2.2, Kotlin 1.9.22, compileSdk 34, JDK 17) | **BUILD SUCCESSFUL**, 807 KB debug APK, signed with debug key (`apksigner verify` OK) |
| Sample app APK `com.amts.sampleapp` | same build | **BUILD SUCCESSFUL**, 800 KB debug APK |

APK verification (`aapt2 dump badging` / `xmltree`): package names, minSdk 26, targetSdk 34, launcher activities `com.amts.companion.MainActivity` / `com.amts.sampleapp.HomeActivity`, AccessibilityService declared with `BIND_ACCESSIBILITY_SERVICE` + `@xml/accessibility_service_config`, **no `uses-permission` entries** (no INTERNET).
Build-environment note: Google ships `aapt2` for Linux only as x86-64. On this aarch64 container it ran under `qemu-x86_64` through `-Pandroid.aapt2FromMavenOverride`. On macOS this is not needed; `./gradlew assembleDebug` is enough.
**Not verified:** installing/launching the APKs on any device, and the accessibility service receiving real events.

## Tests
| Suite | Count | Needs | Result |
|---|---|---|---|
| `backend/tests/test_units.py` | 20 | nothing | pass |
| `backend/tests/test_api_integration.py` | 10 | MongoDB (isolated temp DB) | pass |
| `backend/tests/test_external_api.py` (written by the testing agent) | 16 | running backend at REACT_APP_BACKEND_URL, **no** agent connected | passed in iteration 1 |
| `backend/tests/test_live_agent_external.py` (written by the testing agent) | 2 | running backend + simulated agent, `AMTS_AGENT_RUNNING=1`, `-n 0` | passed in iteration 1 |
| `recorder-agent` JUnit | 21 | nothing | pass (JDK 11 and 17) |
| `tools/fake-adb/run-simulated-e2e.sh` | 3 scenarios | backend + **SIMULATED adb** | pass: normal (TAP HYBRID, masked PIN, BACK), restricted getevent (TAP falls back to ACCESSIBILITY 0.85, limitation reported, no BACK), disconnect → FAILED |

**About the "47 vs 29" numbers:** the old README listed 29 = the self-contained suites (`test_units.py` + `test_api_integration.py`). The earlier completion message's 47 added the 18 environment-dependent tests the testing agent wrote (16 + 2). This iteration adds 1 test (simulated-environment labeling), so it is now **30 self-contained + 18 environment-dependent = 48** backend tests, plus 21 Java tests.

Provenance labeling is fail-closed: `REAL_DEVICE` only when the agent explicitly reports non-simulated adb and the device is not an emulator (`EMULATOR`). A missing flag gives `null`.

Commands:
```bash
cd backend && python -m pytest tests/test_units.py tests/test_api_integration.py -q -n 0
cd backend && python -m pytest tests/test_external_api.py -q -n 0                 # no agent running
cd recorder-agent && mvn -q package
cd recorder-agent && ./tools/fake-adb/run-simulated-e2e.sh http://localhost:8001  # SIMULATED
```
