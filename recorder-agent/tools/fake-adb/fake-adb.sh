#!/usr/bin/env bash
# SIMULATED adb for contract/integration testing of the Recorder Agent WITHOUT a device.
# Output produced through this script is NOT a real recording and must never be presented as one.
# Usage: adb.path=/path/to/fake-adb.sh   (touch $FAKE_ADB_STATE/disconnected to simulate unplug)
DIR="$(cd "$(dirname "$0")" && pwd)"
STATE="${FAKE_ADB_STATE:-/tmp/fake-adb}"
mkdir -p "$STATE"
SERIAL="FAKE-0001"

if [ "$1" = "version" ]; then printf 'Android Debug Bridge version 1.0.41\nVersion 35.0.1-SIMULATED\n'; exit 0; fi
if [ "$1" = "devices" ]; then
  echo "List of devices attached"
  [ -f "$STATE/disconnected" ] || echo "$SERIAL           device usb:1-1 product:fake model:SIMULATED_Pixel device:fake transport_id:1"
  echo; exit 0
fi
[ "$1" = "-s" ] && shift 2
[ -f "$STATE/disconnected" ] && { echo "error: device '$SERIAL' not found" >&2; exit 1; }
MODE="$1"; shift
CMD="$*"
now_ms() { python3 -c 'import time;print(int(time.time()*1000))'; }

case "$MODE:$CMD" in
  shell:getprop*) printf 'SIMULATED Pixel\nSimulated\n14\n34\n' ;;
  shell:"wm size") echo "Physical size: 1080x2400" ;;
  shell:"pm list packages"*) echo "package:com.amts.companion" ;;
  shell:"settings get secure enabled_accessibility_services") echo "com.amts.companion/com.amts.companion.RecorderAccessibilityService" ;;
  shell:"date +%s%3N") now_ms ;;
  shell:"getevent -pl") cat "$DIR/getevent-caps.txt" ;;
  shell:"uiautomator dump"*) echo "UI hierchary dumped to: /sdcard/amts_window_dump.xml" ;;
  exec-out:cat*) cat "$DIR/hierarchy.xml" ;;
  exec-out:"screencap -p") cat "$DIR/screen.png" ;;
  shell:rm*) ;;
  shell:"dumpsys window") echo "  mCurrentFocus=Window{1a2b u0 com.example.testapp/com.example.testapp.TransferActivity}" ;;
  shell:"dumpsys input") echo "    SurfaceOrientation: 0" ;;
  shell:"dumpsys input_method") echo "  mInputShown=false" ;;
  shell:"getevent -lt")
    sleep 4
    for l in "EV_ABS       ABS_MT_TRACKING_ID   00000001" "EV_ABS       ABS_MT_POSITION_X    000000e1" \
             "EV_ABS       ABS_MT_POSITION_Y    000000e6" "EV_KEY       BTN_TOUCH            DOWN" \
             "EV_SYN       SYN_REPORT           00000000"; do echo "[   100.000000] /dev/input/event2: $l"; done
    sleep 0.08
    for l in "EV_ABS       ABS_MT_TRACKING_ID   ffffffff" "EV_KEY       BTN_TOUCH            UP" \
             "EV_SYN       SYN_REPORT           00000000"; do echo "[   100.080000] /dev/input/event2: $l"; done
    sleep 3
    echo "[   107.000000] /dev/input/event1: EV_KEY       KEY_BACK             DOWN"
    echo "[   107.050000] /dev/input/event1: EV_KEY       KEY_BACK             UP"
    sleep 100000 ;;
  logcat:*)
    sleep 4
    T=$(now_ms)
    echo "{\"v\":1,\"type\":\"CLICK\",\"ts\":$T,\"pkg\":\"com.example.testapp\",\"node\":{\"resourceId\":\"com.example.testapp:id/transferButton\",\"text\":\"Transfer\",\"className\":\"android.widget.Button\",\"bounds\":[100,200,350,260],\"clickable\":true,\"enabled\":true,\"password\":false}}"
    sleep 1
    for n in 1 2 3 4; do
      echo "{\"v\":1,\"type\":\"TEXT_CHANGED\",\"ts\":$(now_ms),\"pkg\":\"com.example.testapp\",\"textValue\":null,\"textLength\":$n,\"masked\":true,\"node\":{\"resourceId\":\"com.example.testapp:id/pinInput\",\"className\":\"android.widget.EditText\",\"bounds\":[60,540,1020,620],\"password\":true}}"
      sleep 0.2
    done
    sleep 100000 ;;
  *) echo "fake-adb: unsupported: $MODE $CMD" >&2; exit 1 ;;
esac
