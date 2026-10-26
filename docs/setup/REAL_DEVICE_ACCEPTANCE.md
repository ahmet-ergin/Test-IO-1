# Guided real-device acceptance test (Phase 1)

**Status: NOT RUN.** No physical device was available in the build environment. Only you can mark rows PASS, in `ACCEPTANCE_RESULTS.md`.

Rules for distinguishing results:
* A run counts as a real-device result only if the session's **environment = `REAL_DEVICE`** (shown as a green *REAL DEVICE* tag in Sessions; `"environment"` in the export) and `--diagnose` shows **no** `SIMULATED adb` line.
* `SIMULATED_ADB` sessions (fake-adb) and `DEMO` sessions never count. `EMULATOR` sessions (serial `emulator-*`) are useful but are reported separately from physical-device results. A session with `environment: null` (provenance not reported) does not count.

App under test: **AMTS Sample App** (`com.amts.sampleapp`, synthetic data, no network). Screens: Home (Transfer button, *Long press me* button, 60-item list) → Form (Recipient name, PIN [password], SMS code [number]) → Result.

Prerequisites: steps 0–4 of `LOCAL_VALIDATION.md` done, agent running, companion showing YES/YES.

| ID | Step | Expected result |
|---|---|---|
| A1 Device detection | `java -jar target/recorder-agent.jar --diagnose` then open **Devices** | diagnose: `device <serial> device`, properties PASS. UI: real model, Android version, serial, USB icon, ADB available, state ONLINE |
| A2 Companion activation | companion app screen; Devices column *Companion* | both lines YES (green); UI shows *Etkin/Enabled*; diagnose: `companion events in logcat … SERVICE_CONNECTED seen` |
| A3 Start | Devices → Select; Recorder → package filter `com.amts.sampleapp` → Start (sample app already open on Home) | STARTING → RECORDING within ~5 s; feed: `SCREEN_CHANGE` (ADB_UIAUTOMATOR); latest screen image shows Home |
| A4 TAP | tap **Transfer** | `TAP` with source **HYBRID**, element `com.amts.sampleapp:id/transferButton`, coordinates inside its bounds; then `SCREEN_CHANGE` to FormActivity |
| A5 INPUT_TEXT (plain) | tap *Recipient name*, type `Test User`, wait 2 s | `INPUT_TEXT` element `nameInput`, value `"Test User"` (synthetic, not sensitive) |
| A6 INPUT_TEXT (masked) | tap *PIN*, type `1234`; tap *SMS code*, type `482913` | two `INPUT_TEXT` events shown as `[MASKED · 4]` / `[MASKED · 6]`, `value: null`, reasons PASSWORD_FIELD / OTP/keyword. Keyboard taps are **not** recorded as TAPs (count listed in limitations) |
| A7 BACK | press system BACK (3-button navigation) | `BACK` (ADB_GETEVENT). With gesture navigation: a `SWIPE` from the screen edge + limitation (documented unsupported) |
| A8 SCROLL | on Home, swipe the list up | `SCROLL` with source HYBRID (or ACCESSIBILITY) on `itemList`, start/end coordinates if getevent available |
| A9 LONG_PRESS (optional) | long-press *Long press me* | `LONG_PRESS` element with contentDesc `long_press_target` |
| A10 Pause/Resume | Pause, tap Transfer, Resume | nothing recorded while PAUSED; duration frozen |
| A11 Stop/Save | Stop → Save | COMPLETED, *SAVED* tag in Sessions, tag *REAL DEVICE* |
| A12 Hierarchy & screenshot association | Recorded Steps → Inspect a TAP → tabs | *Event JSON* has `screenId`, `hierarchyRef`, `screenshotRef`; *Hierarchy XML* contains the tapped node; *Screenshot* shows red tap point + blue element box |
| A13 Locator extraction | Inspect Details for the Transfer TAP | candidates RESOURCE_ID `com.amts.sampleapp:id/transferButton` (unique), UIAUTOMATOR text selector, XPATH (lower), COORDINATES (lowest); XPath is not first |
| A14 JSON export | Export JSON, then validate (below) | valid; `sequence` strictly increasing; ISO timestamps; `environment: "REAL_DEVICE"` |
| A15 No secret leakage | `grep -E "1234\|482913" recording-<id>.json` and Inspect → XML of the form screen | no matches; PIN/SMS node text `[MASKED]` |
| A16 Disconnect | start a new recording, then unplug USB | within ~2–3 s session **BAŞARISIZ/FAILED**, error "Android device disconnected during recording."; device row → Offline. Replug → ONLINE again |
| A17 Agent stop | Ctrl-C the agent | within ~10 s header amber "Local Recorder Agent is not connected."; no devices listed |
| A18 ADB-only fallback (optional) | disable the companion service, record A4 again | TAP source ADB_GETEVENT, confidence 0.6, limitation "Companion AccessibilityService not enabled…" |

Validate the export:
```bash
python3 -m pip install jsonschema
python3 - <<'EOF'
import json, jsonschema, sys
doc = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "recording.json"))
jsonschema.validate(doc, json.load(open("shared/contracts/recording-session.v1.schema.json")))
seq = [e["sequence"] for e in doc["events"]]
assert seq == sorted(seq) and len(set(seq)) == len(seq), "sequence not strictly increasing"
print("VALID", doc["environment"], len(doc["events"]), "events")
EOF
```
(Run as `python3 validate.py recording-<id>.json` after saving the snippet as validate.py.)

Record the results in `docs/setup/ACCEPTANCE_RESULTS.md`, and attach the exported JSON plus agent log (`java -jar ... 2>&1 | tee agent.log`).
