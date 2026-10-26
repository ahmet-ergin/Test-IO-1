package com.amts.agent;

import com.amts.agent.adb.AdbClient;
import com.amts.agent.adb.AdbParsers;
import com.amts.agent.capture.ScreenCapturer;
import com.amts.agent.events.CompanionEvent;
import com.amts.agent.events.CoordinateMapper;
import com.amts.agent.events.GeteventParser;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * Local device diagnostics (no backend needed): `java -jar recorder-agent.jar --diagnose [--adb PATH] [--serial S] [--watch SECONDS]`.
 * Prints PASS / WARN / FAIL per capability so real-device results are explicit.
 */
public final class Diagnostics {
    private final AdbClient adb;
    private final String companionPkg;
    private int fails;

    private Diagnostics(String adbPath, String companionPkg) {
        this.adb = new AdbClient(adbPath);
        this.companionPkg = companionPkg;
    }

    public static void run(String[] args) throws Exception {
        String adbPath = "adb", serial = null, pkg = "com.amts.companion";
        int watch = 0;
        for (int i = 1; i < args.length - 1; i++) {
            if (args[i].equals("--adb")) adbPath = args[++i];
            else if (args[i].equals("--serial")) serial = args[++i];
            else if (args[i].equals("--watch")) watch = Integer.parseInt(args[++i]);
            else if (args[i].equals("--companion")) pkg = args[++i];
        }
        Diagnostics d = new Diagnostics(adbPath, pkg);
        d.check(serial, watch);
        System.out.println(d.fails == 0 ? "\nRESULT: no blocking failures" : "\nRESULT: " + d.fails + " blocking failure(s)");
        System.exit(d.fails == 0 ? 0 : 1);
    }

    private void out(String level, String what, String detail) {
        if (level.equals("FAIL")) fails++;
        System.out.printf("[%-4s] %-34s %s%n", level, what, detail == null ? "" : detail);
    }

    private void check(String serial, int watch) throws Exception {
        System.out.println("AI Mobile Test Studio - Recorder Agent diagnostics " + AgentApp.VERSION
                + " (java " + System.getProperty("java.version") + ", " + System.getProperty("os.name") + ")");
        String version;
        try {
            version = adb.version();
            out("PASS", "adb available", version);
        } catch (Exception e) {
            out("FAIL", "adb available", e.getMessage() + "  -> install platform-tools / set --adb");
            return;
        }
        if (version.contains("SIMULATED")) out("WARN", "SIMULATED adb", "results below are NOT from a real device");
        List<AdbParsers.DeviceLine> devices = AdbParsers.parseDevices(adb.run(5000, "devices", "-l").text());
        if (devices.isEmpty()) {
            out("FAIL", "device detected", "no devices -> enable USB debugging, check cable, `adb devices`");
            return;
        }
        for (AdbParsers.DeviceLine l : devices) out(l.state.equals("device") ? "PASS" : "WARN", "device " + l.serial, l.state + " " + l.attrs);
        String s = serial != null ? serial : devices.stream().filter(l -> l.state.equals("device")).map(l -> l.serial).findFirst().orElse(null);
        if (s == null) {
            out("FAIL", "authorized device", "accept the USB debugging prompt on the device");
            return;
        }
        String props = adb.shell(s, 5000, "getprop ro.product.model; getprop ro.build.version.release; getprop ro.build.version.sdk").text().replaceAll("\\R", " | ");
        out("PASS", "device properties", props);
        int[] size = AdbParsers.parseWmSize(adb.shell(s, 5000, "wm size").text());
        out(size != null ? "PASS" : "WARN", "screen size", size == null ? "unavailable" : size[0] + "x" + size[1]);
        boolean installed = adb.shell(s, 5000, "pm list packages " + companionPkg).text().contains("package:" + companionPkg);
        boolean enabled = adb.shell(s, 5000, "settings get secure enabled_accessibility_services").text().contains(companionPkg + "/");
        out(installed ? "PASS" : "WARN", "companion installed", installed ? companionPkg : "not installed -> ADB-only mode");
        out(enabled ? "PASS" : "WARN", "companion accessibility enabled", enabled ? "yes" : "no -> enable in Settings > Accessibility");
        AdbClient.Result caps = adb.shell(s, 8000, "getevent -pl");
        Map<String, int[]> touch = AdbParsers.parseTouchDevices(caps.text());
        boolean denied = (caps.text() + caps.stderr).contains("Permission denied");
        if (!touch.isEmpty()) out("PASS", "getevent touchscreen", touch.keySet() + (denied ? " (some input devices denied)" : ""));
        else out("WARN", "getevent touchscreen", "not readable" + (denied ? " (permission denied)" : "") + " -> no raw coordinates; root is NOT used");
        ScreenCapturer cap = new ScreenCapturer(adb, s);
        try {
            long t0 = System.currentTimeMillis();
            ScreenCapturer.Snapshot snap = cap.capture(true, false, List.of(), null);
            out("PASS", "uiautomator hierarchy dump", snap.index.nodes.size() + " nodes, " + (System.currentTimeMillis() - t0) + " ms, pkg=" + snap.packageName);
            out(snap.activity != null ? "PASS" : "WARN", "current activity", String.valueOf(snap.activity));
            out(snap.orientation != null ? "PASS" : "WARN", "orientation", String.valueOf(snap.orientation));
            String st = snap.screenshotStatus;
            out("CAPTURED".equals(st) ? "PASS" : "WARN", "screenshot", st + (snap.limitations.isEmpty() ? "" : " " + snap.limitations));
        } catch (Exception e) {
            out("FAIL", "uiautomator hierarchy dump", e.getMessage() + " -> stop Appium/UiAutomator2 sessions, unlock screen");
        }
        String logs = adb.run(8000, "-s", s, "logcat", "-d", "-v", "raw", "-s", "AMTS_EVT:I").text();
        long lines = logs.lines().filter(x -> x.contains("\"v\":1")).count();
        out(lines > 0 ? "PASS" : (enabled ? "WARN" : "INFO"), "companion events in logcat", lines + " line(s)"
                + (logs.contains("SERVICE_CONNECTED") ? ", SERVICE_CONNECTED seen" : ""));
        if (watch > 0) watch(s, touch, size, watch);
    }

    private void watch(String s, Map<String, int[]> touch, int[] size, int seconds) throws Exception {
        System.out.println("\nWATCH " + seconds + "s: interact with the device now (tap, type, scroll, BACK)...");
        CoordinateMapper mapper = touch.isEmpty() || size == null ? null
                : new CoordinateMapper(touch.values().iterator().next()[0], touch.values().iterator().next()[1], size[0], size[1]);
        GeteventParser parser = new GeteventParser(touch.keySet(), new GeteventParser.Listener() {
            public void onTouch(GeteventParser.RawTouch t) {
                int[] p = mapper.map(t.startX, t.startY, 0);
                System.out.printf("  getevent  touch at (%d,%d) %dms%s%n", p[0], p[1], t.durationMs, t.multiTouch ? " multi" : "");
            }

            public void onKey(String key, long ms) {
                System.out.println("  getevent  key " + key);
            }
        });
        Process ge = mapper == null ? null : adb.stream(s, "shell", "getevent", "-lt");
        Process lc = adb.stream(s, "logcat", "-T", "1", "-v", "raw", "-s", "AMTS_EVT:I");
        if (ge != null) pump(ge, l -> parser.accept(l, System.currentTimeMillis()));
        pump(lc, l -> {
            CompanionEvent e = CompanionEvent.parse(l, 0);
            if (e != null) System.out.println("  companion " + e.type + " pkg=" + e.pkg + " id=" + (e.node == null ? null : e.node.get("resourceId"))
                    + (e.type.equals("TEXT_CHANGED") ? " masked=" + e.masked + " len=" + e.textLength : ""));
        });
        Thread.sleep(seconds * 1000L);
        if (ge != null) ge.destroy();
        lc.destroy();
    }

    private static void pump(Process p, java.util.function.Consumer<String> c) {
        Thread t = new Thread(() -> {
            try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) c.accept(line);
            } catch (Exception ignored) {
                // stream closed
            }
        });
        t.setDaemon(true);
        t.start();
    }
}
