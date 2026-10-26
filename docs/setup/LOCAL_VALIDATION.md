# Local setup & real-device acceptance test (macOS)

> Real-device acceptance criteria are **NOT yet passed**. They require the steps below on your Mac with a physical Android device.

## Requirements
* macOS, JDK 11+ (`java -version`), Maven 3.8+, Android platform-tools (`adb version`)
* Android Studio (or Android SDK + Gradle 8) to build the companion APK, minSdk 26 (Android 8)
* A test Android device with Developer options + USB debugging, a **test build** of the app and synthetic data
* Stop any Appium/UiAutomator2 session on the device while recording (it blocks `uiautomator dump`)

## 1. Pair the agent
1. Open the web UI → **Settings → Agent Pairing → Generate New Token** (shown once).
2. `cp recorder-agent/agent.properties.example recorder-agent/agent.properties` and paste `backend.url` and `agent.token`. The file is git-ignored.

## 2. Build & start the agent
```bash
cd recorder-agent
mvn -q package                      # runs 21 unit tests
java -jar target/recorder-agent.jar agent.properties
```
Expected log: `AI Mobile Test Studio Recorder Agent 0.1.0 -> https://...`. The UI header turns green.

## 3. Build & enable the companion (recommended)
```bash
cd android-companion
gradle wrapper && ./gradlew assembleDebug      # or open the folder in Android Studio
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
On the device: Settings → Accessibility → *AI Mobile Test Studio Recorder* → On. (Or `adb shell settings put secure enabled_accessibility_services com.amts.companion/com.amts.companion.RecorderAccessibilityService` + `adb shell settings put secure accessibility_enabled 1`.)
Check: `adb logcat -s AMTS_EVT:I` prints JSON lines when you tap.
Devices page → column *Companion* = **Enabled**.

## 4. Acceptance checklist
| # | Check | How |
|---|---|---|
| D1 | Agent starts on macOS | step 2 |
| D2 | Device detected | Devices page shows model, Android version, serial, USB, ADB available |
| D3 | Unauthorized handled | revoke USB debugging authorizations → row shows UNAUTHORIZED + hint |
| D4 | Disconnect handled | during a recording unplug USB → session **FAILED / DEVICE_DISCONNECTED** within ~2 s; device shows Offline |
| R1 | Start | Devices → Select → Recorder → Start Recording → status RECORDING, initial SCREEN_CHANGE appears |
| R2 | Real actions | tap a button, type into a text field, type into a password field, scroll a list, press BACK |
| R3 | Captured | Live feed shows TAP (HYBRID), INPUT_TEXT, INPUT_TEXT `[MASKED · n]`, SCROLL, BACK, SCREEN_CHANGE |
| R4 | Snapshots | Latest screen updates; events reference screenshots/XML (Recorded Steps → Inspect → tabs) |
| R5 | Pause/Resume | actions during PAUSED are not recorded |
| R6 | Stop + Save | Stop → COMPLETED → Save Session |
| J1 | Valid JSON | Export JSON; validate: `python3 -c "import json,jsonschema;jsonschema.validate(json.load(open('recording-<id>.json')),json.load(open('shared/contracts/recording-session.v1.schema.json')))"` |
| J2 | Sequence/timestamps | `sequence` strictly increasing, ISO timestamps |
| J3 | Missing metadata | ACCESSIBILITY-only taps have `coordinates: null`; uncertain taps flagged |
| J4 | Masking | no password/OTP value appears anywhere in the export or XML artifacts |
| S1 | FLAG_SECURE app | screenshotStatus `BLOCKED_SECURE`, no image stored |
| S2 | ADB-only mode | disable the companion → recording still works, limitation banner shown, lower confidence |

Record results (device model, Android version, app, pass/fail per row) in `docs/setup/ACCEPTANCE_RESULTS.md`.

## Simulated contract test (no device)
`recorder-agent/tools/fake-adb/fake-adb.sh` is a **simulated adb** used only to test agent ⇄ backend contracts. Set `adb.path` to it. Its output is synthetic and must never be reported as a real recording.

## Backend tests
```bash
cd backend && python -m pytest tests -q     # 29 tests: state machine, masking, locators, API flow, disconnect, schema
```
