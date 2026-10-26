package com.amts.agent.device;

import com.amts.agent.adb.AdbClient;
import com.amts.agent.adb.AdbParsers;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

/** Discovers devices via `adb devices -l`; caches slow per-device properties. */
public class DeviceDiscovery {
    private static final Logger LOG = Logger.getLogger(DeviceDiscovery.class.getName());
    private static final long PROPS_TTL_MS = 10_000;
    private final AdbClient adb;
    private final String companionPackage;
    private final Map<String, Map<String, Object>> cache = new ConcurrentHashMap<>();
    private final Map<String, Long> cacheTime = new ConcurrentHashMap<>();

    public DeviceDiscovery(AdbClient adb, String companionPackage) {
        this.adb = adb;
        this.companionPackage = companionPackage;
    }

    public void invalidate() {
        cache.clear();
        cacheTime.clear();
    }

    public List<Map<String, Object>> discover() throws Exception {
        AdbClient.Result r = adb.run(5000, "devices", "-l");
        if (!r.ok()) throw new IllegalStateException("adb devices failed: " + r.stderr);
        List<Map<String, Object>> out = new ArrayList<>();
        for (AdbParsers.DeviceLine line : AdbParsers.parseDevices(r.text())) {
            Map<String, Object> d = new LinkedHashMap<>();
            d.put("serial", line.serial);
            d.put("state", line.state);
            d.put("connectionType", line.serial.contains(":") || line.serial.contains("._adb-tls") ? "WIFI" : "USB");
            String model = line.attrs.get("model");
            d.put("model", model == null ? null : model.replace('_', ' '));
            if ("device".equals(line.state)) d.putAll(properties(line.serial));
            out.add(d);
        }
        return out;
    }

    private Map<String, Object> properties(String serial) {
        Long t = cacheTime.get(serial);
        if (t != null && System.currentTimeMillis() - t < PROPS_TTL_MS) return cache.get(serial);
        Map<String, Object> p = new LinkedHashMap<>();
        try {
            String[] lines = adb.shell(serial, 5000, "getprop ro.product.model; getprop ro.product.manufacturer; "
                    + "getprop ro.build.version.release; getprop ro.build.version.sdk").text().split("\\R");
            if (lines.length >= 4) {
                p.put("model", blankToNull(lines[0]));
                p.put("manufacturer", blankToNull(lines[1]));
                p.put("androidVersion", blankToNull(lines[2]));
                p.put("sdkInt", parseIntOrNull(lines[3]));
            }
            int[] size = AdbParsers.parseWmSize(adb.shell(serial, 5000, "wm size").text());
            if (size != null) {
                p.put("screenWidth", size[0]);
                p.put("screenHeight", size[1]);
            }
            String pkgs = adb.shell(serial, 5000, "pm list packages " + companionPackage).text();
            p.put("companionInstalled", pkgs.contains("package:" + companionPackage));
            String enabled = adb.shell(serial, 5000, "settings get secure enabled_accessibility_services").text();
            p.put("companionEnabled", enabled.contains(companionPackage + "/"));
        } catch (Exception e) {
            LOG.warning("Could not read properties for " + serial + ": " + e.getMessage());
        }
        cache.put(serial, p);
        cacheTime.put(serial, System.currentTimeMillis());
        return p;
    }

    private static String blankToNull(String s) {
        return s == null || s.trim().isEmpty() ? null : s.trim();
    }

    private static Integer parseIntOrNull(String s) {
        try {
            return Integer.parseInt(s.trim());
        } catch (Exception e) {
            return null;
        }
    }
}
