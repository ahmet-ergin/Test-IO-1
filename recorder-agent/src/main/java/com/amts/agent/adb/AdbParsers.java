package com.amts.agent.adb;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Pure parsing helpers for adb/dumpsys output (unit-tested without a device). */
public final class AdbParsers {
    private AdbParsers() {
    }

    public static final class DeviceLine {
        public final String serial;
        public final String state;
        public final Map<String, String> attrs;

        DeviceLine(String serial, String state, Map<String, String> attrs) {
            this.serial = serial;
            this.state = state;
            this.attrs = attrs;
        }
    }

    public static String parseAdbVersion(String out) {
        Matcher m = Pattern.compile("Android Debug Bridge version ([\\d.]+)").matcher(out);
        Matcher v = Pattern.compile("Version ([\\w.\\-]+)").matcher(out);
        String base = m.find() ? m.group(1) : "unknown";
        return v.find() ? base + " (" + v.group(1) + ")" : base;
    }

    public static List<DeviceLine> parseDevices(String out) {
        List<DeviceLine> list = new ArrayList<>();
        for (String raw : out.split("\\R")) {
            String line = raw.trim();
            if (line.isEmpty() || line.startsWith("List of devices") || line.startsWith("*")) continue;
            String[] parts = line.split("\\s+");
            if (parts.length < 2) continue;
            Map<String, String> attrs = new HashMap<>();
            for (int i = 2; i < parts.length; i++) {
                int idx = parts[i].indexOf(':');
                if (idx > 0) attrs.put(parts[i].substring(0, idx), parts[i].substring(idx + 1));
            }
            list.add(new DeviceLine(parts[0], parts[1], attrs));
        }
        return list;
    }

    /** Parses "Physical size: 1080x2400" (and prefers "Override size" when present). */
    public static int[] parseWmSize(String out) {
        int[] physical = null;
        int[] override = null;
        Matcher m = Pattern.compile("(Physical|Override) size:\\s*(\\d+)x(\\d+)").matcher(out);
        while (m.find()) {
            int[] v = {Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3))};
            if (m.group(1).equals("Physical")) physical = v;
            else override = v;
        }
        return override != null ? override : physical;
    }

    /** Returns [package, activity] from dumpsys window output, or null. */
    public static String[] parseFocusedWindow(String out) {
        Pattern[] patterns = {
                Pattern.compile("mCurrentFocus=Window\\{\\S+ \\S+ ([\\w.]+)/([\\w.$]+)\\}"),
                Pattern.compile("mFocusedApp=.*?ActivityRecord\\{\\S+ \\S+ ([\\w.]+)/([\\w.$]+)"),
        };
        for (Pattern p : patterns) {
            Matcher m = p.matcher(out);
            if (m.find()) {
                String act = m.group(2);
                if (act.startsWith(".")) act = m.group(1) + act;
                return new String[]{m.group(1), act};
            }
        }
        return null;
    }

    public static Integer parseOrientation(String dumpsysInput) {
        Matcher m = Pattern.compile("SurfaceOrientation:\\s*(\\d)").matcher(dumpsysInput);
        if (m.find()) return Integer.parseInt(m.group(1));
        Matcher r = Pattern.compile("mCurrentRotation=(?:ROTATION_)?(\\d+)").matcher(dumpsysInput);
        if (r.find()) {
            int v = Integer.parseInt(r.group(1));
            return v >= 90 ? v / 90 : v;
        }
        return null;
    }

    public static boolean parseImeShown(String dumpsysInputMethod) {
        return dumpsysInputMethod.contains("mInputShown=true") || dumpsysInputMethod.contains("isInputViewShown=true");
    }

    /** Parses `getevent -pl`: maps touchscreen device path to [maxX, maxY]. */
    public static Map<String, int[]> parseTouchDevices(String out) {
        Map<String, int[]> result = new HashMap<>();
        String current = null;
        Integer maxX = null;
        Integer maxY = null;
        Pattern add = Pattern.compile("add device \\d+: (\\S+)");
        Pattern max = Pattern.compile("max (\\d+)");
        for (String line : out.split("\\R")) {
            Matcher a = add.matcher(line);
            if (a.find()) {
                if (current != null && maxX != null && maxY != null) result.put(current, new int[]{maxX, maxY});
                current = a.group(1);
                maxX = null;
                maxY = null;
                continue;
            }
            Matcher mm = max.matcher(line);
            if (line.contains("ABS_MT_POSITION_X") && mm.find()) maxX = Integer.parseInt(mm.group(1));
            else if (line.contains("ABS_MT_POSITION_Y") && mm.find()) maxY = Integer.parseInt(mm.group(1));
        }
        if (current != null && maxX != null && maxY != null) result.put(current, new int[]{maxX, maxY});
        return result;
    }
}
