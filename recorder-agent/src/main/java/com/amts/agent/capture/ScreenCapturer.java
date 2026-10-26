package com.amts.agent.capture;

import com.amts.agent.adb.AdbClient;
import com.amts.agent.adb.AdbParsers;
import com.amts.agent.events.SensitiveMasker;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Logger;

/** Captures UI hierarchy + screenshot + window metadata through ADB. Never bypasses FLAG_SECURE. */
public class ScreenCapturer {
    private static final Logger LOG = Logger.getLogger(ScreenCapturer.class.getName());
    private static final String DUMP_PATH = "/sdcard/amts_window_dump.xml";
    private final AdbClient adb;
    private final String serial;

    public ScreenCapturer(AdbClient adb, String serial) {
        this.adb = adb;
        this.serial = serial;
    }

    public static final class Snapshot {
        public long capturedAtMs;
        public String xml;
        public HierarchyIndex index;
        public String structuralHash;
        public String packageName, activity;
        public Integer width, height, orientation;
        public byte[] screenshotPng;
        public String screenshotStatus;
        public final List<String> limitations = new ArrayList<>();
        public String screenId, hierarchyRef, screenshotRef;

        public String capturedAtIso() {
            return Instant.ofEpochMilli(capturedAtMs).toString();
        }
    }

    /** Returns null when the hierarchy is identical to previousXml (no repeated screenshots). */
    public Snapshot capture(boolean screenshot, boolean redact, List<String> keywords, String previousXml)
            throws Exception {
        Snapshot s = new Snapshot();
        s.capturedAtMs = System.currentTimeMillis();
        s.xml = dumpHierarchy();
        if (s.xml.equals(previousXml)) return null;
        s.index = new HierarchyIndex(s.xml);
        s.structuralHash = s.index.structuralHash();
        String[] focus = AdbParsers.parseFocusedWindow(adb.shell(serial, 5000, "dumpsys window").text());
        s.packageName = focus != null ? focus[0] : s.index.rootPackage;
        s.activity = focus != null ? focus[1] : null;
        if (focus == null) s.limitations.add("Current activity unavailable from dumpsys window.");
        s.orientation = AdbParsers.parseOrientation(adb.shell(serial, 5000, "dumpsys input").text());
        int[] size = AdbParsers.parseWmSize(adb.shell(serial, 5000, "wm size").text());
        if (size != null) {
            boolean landscape = s.orientation != null && s.orientation % 2 == 1;
            s.width = landscape ? size[1] : size[0];
            s.height = landscape ? size[0] : size[1];
        }
        if (screenshot) captureScreenshot(s, redact, keywords);
        else s.screenshotStatus = "DISABLED";
        return s;
    }

    private String dumpHierarchy() throws Exception {
        Exception last = null;
        for (int attempt = 0; attempt < 3; attempt++) {
            AdbClient.Result r = adb.shell(serial, 15000, "uiautomator dump " + DUMP_PATH);
            if (r.ok() && r.text().contains("dumped")) {
                byte[] xml = adb.execOut(serial, 10000, "cat " + DUMP_PATH);
                adb.shell(serial, 5000, "rm -f " + DUMP_PATH);
                return new String(xml, StandardCharsets.UTF_8);
            }
            last = new IllegalStateException("uiautomator dump failed: " + r.text().trim() + " " + r.stderr.trim());
            Thread.sleep(400);
        }
        throw last;
    }

    private void captureScreenshot(Snapshot s, boolean redact, List<String> keywords) {
        try {
            byte[] png = adb.execOut(serial, 10000, "screencap -p");
            BufferedImage img = ImageIO.read(new ByteArrayInputStream(png));
            if (img == null) {
                s.screenshotStatus = "FAILED";
                s.limitations.add("Screenshot could not be decoded.");
                return;
            }
            if (isBlank(img)) {
                s.screenshotStatus = "BLOCKED_SECURE";
                s.limitations.add("Screenshot is blank: app likely uses FLAG_SECURE. Not bypassed by design.");
                return;
            }
            List<int[]> regions = redact ? SensitiveMasker.sensitiveBounds(s.index.nodes, keywords) : List.of();
            if (!regions.isEmpty()) {
                Graphics2D g = img.createGraphics();
                g.setColor(Color.BLACK);
                for (int[] b : regions) g.fillRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
                g.dispose();
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                ImageIO.write(img, "png", out);
                png = out.toByteArray();
                s.screenshotStatus = "REDACTED";
            } else {
                s.screenshotStatus = "CAPTURED";
            }
            s.screenshotPng = png;
        } catch (Exception e) {
            LOG.warning("Screenshot failed: " + e.getMessage());
            s.screenshotStatus = "FAILED";
            s.limitations.add("Screenshot failed: " + e.getMessage());
        }
    }

    static boolean isBlank(BufferedImage img) {
        int stepX = Math.max(1, img.getWidth() / 24), stepY = Math.max(1, img.getHeight() / 24);
        for (int x = 0; x < img.getWidth(); x += stepX) {
            for (int y = 0; y < img.getHeight(); y += stepY) {
                int rgb = img.getRGB(x, y);
                if (((rgb >> 16) & 0xff) > 8 || ((rgb >> 8) & 0xff) > 8 || (rgb & 0xff) > 8) return false;
            }
        }
        return true;
    }
}
