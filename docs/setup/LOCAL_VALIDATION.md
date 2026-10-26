# Running AI Mobile Test Studio on your Mac (Phase 1)

Everything that touches the phone runs **on your Mac**. The web UI/backend can be the hosted preview or a local copy.

## 0. One-time tool installation (Homebrew)
```bash
brew install --cask temurin@17            # JDK 17: required by Android Gradle Plugin 8.2 to BUILD the APK
brew install --cask temurin@11            # optional: run the agent on exactly Java 11 (it also runs on 17+)
brew install maven                        # Maven 3.8+
brew install --cask android-platform-tools  # adb
# Android SDK (pick one): Android Studio (SDK at ~/Library/Android/sdk), or:
brew install --cask android-commandlinetools
sdkmanager "platforms;android-34" "build-tools;34.0.0"
```
Check: `java -version`, `mvn -v`, `adb version`.
List installed JDKs: `/usr/libexec/java_home -V`. Select one per shell: `export JAVA_HOME=$(/usr/libexec/java_home -v 17)`.

## 1. Phone preparation (test device only, synthetic data)
1. Settings → About phone → tap *Build number* 7× → Developer options → **USB debugging ON**.
2. Connect USB, accept the *Allow USB debugging* prompt, check `adb devices -l` shows `device` (not `unauthorized`).
3. Unlock the screen and keep it on (Developer options → *Stay awake*).
4. Close any Appium / UiAutomator2 session (it blocks `uiautomator dump` and accessibility capture).

## 2. Build & install the companion + sample app
```bash
cd android-companion
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties     # adjust if your SDK is elsewhere
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk                 # AMTS Recorder Companion
adb install -r sample-app/build/outputs/apk/debug/sample-app-debug.apk   # AMTS Sample App (non-sensitive test app)
```
Prebuilt debug APKs (built in the Linux CI environment, see `docs/TEST_REPORT.md`) are also in `android-companion/prebuilt/` — verify with `shasum -a 256 -c android-companion/prebuilt/SHA256SUMS`. Building yourself is preferred.

Enable the accessibility service (either way):
* UI: open **AMTS Recorder Companion** → *Open Accessibility Settings* → *AI Mobile Test Studio Recorder* → On.
* adb:
  ```bash
  adb shell settings put secure enabled_accessibility_services com.amts.companion/com.amts.companion.RecorderAccessibilityService
  adb shell settings put secure accessibility_enabled 1
  ```
  (This overwrites other enabled services; use the UI if you rely on others.)

Verify in the companion app: *Enabled in Accessibility settings: YES* and *Service connected (running): YES* (both green). Tapping in another app increases *Events emitted*.
If the toggle is greyed out (Android 13+ "Restricted setting"): App info → ⋮ → *Allow restricted settings*, then retry.

## 3. Build & check the Recorder Agent
```bash
cd recorder-agent
export JAVA_HOME=$(/usr/libexec/java_home -v 11)   # or 17
mvn -q package                                      # compiles for Java 11 (--release 11) + runs 21 unit tests
java -jar target/recorder-agent.jar --diagnose --watch 20
```
`--diagnose` needs no backend. It prints PASS/WARN/FAIL for adb, device state, properties, companion installed/enabled, getevent access, hierarchy dump, activity, orientation, screenshot (BLOCKED_SECURE if the screen is protected) and companion logcat transport. With `--watch 20` tap/type/scroll/BACK on the phone and watch raw `getevent` touches and `companion` events print live. Options: `--serial <id>`, `--adb <path>`.

## 4. Pair and run the agent
1. Web UI → **Settings → Agent Pairing → Generate New Token** (shown once).
2. `cp agent.properties.example agent.properties` and set `backend.url` (the URL shown in the snippet) and `agent.token`. `agent.properties` is git-ignored.
3. `java -jar target/recorder-agent.jar agent.properties` — keep it running. The header turns green ("Yerel Kayıt Ajanı Bağlı").

## 5. Record
Devices → select your device (Companion = *Enabled*) → Recorder → optional package filter `com.amts.sampleapp` → **Kaydı Başlat / Start Recording** → use the phone → **Durdur / Stop** → **Oturumu Kaydet / Save** → **JSON Dışa Aktar / Export**.
Then follow the acceptance script: `docs/setup/REAL_DEVICE_ACCEPTANCE.md`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Agent log `401 ... check agent.token` | regenerate the token, update agent.properties, restart agent |
| Device `unauthorized` | accept the prompt on the phone; `adb kill-server && adb devices` |
| `uiautomator dump failed` | unlock the screen, stop Appium/UiAutomator2, avoid long animations |
| No companion events | companion app must show both YES; run `adb logcat -s AMTS_EVT:I` |
| getevent WARN | some OEMs block `getevent` without root; recording continues companion-only (no coordinates, no hardware BACK). Root is never used. |
| Screenshot BLOCKED_SECURE | app uses FLAG_SECURE; by design not bypassed, hierarchy still captured |
