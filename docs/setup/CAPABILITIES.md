# Recording capabilities: supported vs unsupported (Phase 1, Android)

| Capability | With companion + getevent | Companion only (getevent restricted) | ADB only (no companion) |
|---|---|---|---|
| TAP / LONG_PRESS | HYBRID 0.95, element + coordinates | ACCESSIBILITY 0.85, element, **no coordinates** | ADB_GETEVENT 0.6, element from last snapshot (may be stale) |
| INPUT_TEXT | value captured; password/keyword/OTP fields **masked** (value null, length only) | same | **not captured** |
| SCROLL | HYBRID with start/end points | ACCESSIBILITY (no points) | SWIPE (ADB_GETEVENT) |
| SWIPE | ADB_GETEVENT | **not captured** | ADB_GETEVENT |
| BACK (3-button / hardware key) | ADB_GETEVENT | **not captured** | ADB_GETEVENT |
| SCREEN_CHANGE | hierarchy polling + window events | same | hierarchy polling |
| KEYBOARD_ACTION | hardware ENTER/TAB/SEARCH only | **not captured** | hardware only |
| Hierarchy XML, activity, orientation, size | yes | yes | yes |
| Screenshot | yes; FLAG_SECURE → BLOCKED_SECURE | same | same |

Not supported in Phase 1, in any mode: soft-keyboard IME actions (Done/Next/Search keys), gesture-navigation BACK (shows up as an edge SWIPE plus a limitation), pinch and multi-finger gestures (first pointer only, flagged), WebView/Flutter/game content without accessibility nodes, views marked `accessibilityDataSensitive` (Android 14+), apps that refuse to run while an accessibility service is enabled, WAIT/ASSERTION events (schema only; verification points are set on steps), root-only input devices (root is never used), iOS.

Each session reports the limitations that applied to it (Recorder → *Capture Limitations*, and `limitations` in the export).
