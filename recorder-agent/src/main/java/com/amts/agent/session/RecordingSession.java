package com.amts.agent.session;

import com.amts.agent.adb.AdbClient;
import com.amts.agent.adb.AdbParsers;
import com.amts.agent.capture.HierarchyIndex;
import com.amts.agent.capture.ScreenCapturer;
import com.amts.agent.capture.ScreenCapturer.Snapshot;
import com.amts.agent.events.CompanionEvent;
import com.amts.agent.events.CoordinateMapper;
import com.amts.agent.events.EventCorrelator;
import com.amts.agent.events.GeteventParser;
import com.amts.agent.events.SensitiveMasker;
import com.amts.agent.events.TouchGesture;
import com.amts.agent.transport.BackendClient;
import com.fasterxml.jackson.databind.JsonNode;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Level;
import java.util.logging.Logger;

/** One recording on one device: getevent + companion logcat + hierarchy capture, correlated into events. */
public class RecordingSession {
    private static final Logger LOG = Logger.getLogger(RecordingSession.class.getName());
    private static final String COMPANION_TAG = "AMTS_EVT";

    public final String id;
    public final String serial;
    private final String packageFilter;
    private final long captureIntervalMs;
    private final boolean screenshots, redact;
    private final List<String> keywords;
    private final AdbClient adb;
    private final BackendClient backend;
    private final String companionPackage;
    private final ScreenCapturer capturer;
    private final List<Snapshot> snapshots = new CopyOnWriteArrayList<>();
    private final LinkedBlockingQueue<Map<String, Object>> outbox = new LinkedBlockingQueue<>();
    private final AtomicInteger sequence = new AtomicInteger();
    private final AtomicBoolean captureBusy = new AtomicBoolean();
    private final List<String> limitations = new CopyOnWriteArrayList<>();
    private final List<Process> streams = new ArrayList<>();
    private final ScheduledExecutorService ticker = Executors.newScheduledThreadPool(2);
    private final ExecutorService captureExec = Executors.newSingleThreadExecutor();

    private EventCorrelator correlator;
    private CoordinateMapper mapper;
    private boolean companionActive;
    private volatile boolean paused, stopped;
    private volatile long lastCaptureMs, captureRequestedAt = Long.MAX_VALUE, startedAtMs, clockOffsetMs;
    private volatile int[] imeBounds;
    private volatile boolean imeShownFallback;
    private final AtomicInteger keyboardTouches = new AtomicInteger(), filteredByPackage = new AtomicInteger();

    @SuppressWarnings("unchecked")
    public RecordingSession(String id, JsonNode payload, AdbClient adb, BackendClient backend, String companionPackage) {
        this.id = id;
        this.serial = payload.path("deviceSerial").asText();
        this.packageFilter = payload.hasNonNull("packageFilter") ? payload.get("packageFilter").asText() : null;
        JsonNode s = payload.path("settings");
        this.captureIntervalMs = s.path("capture_interval_ms").asLong(3000);
        this.screenshots = s.path("capture_screenshots").asBoolean(true);
        this.redact = s.path("redact_sensitive_regions").asBoolean(true);
        this.keywords = BackendClient.JSON.convertValue(s.path("mask_keywords"), List.class);
        this.adb = adb;
        this.backend = backend;
        this.companionPackage = companionPackage;
        this.capturer = new ScreenCapturer(adb, serial);
    }

    public void start() throws Exception {
        startedAtMs = System.currentTimeMillis();
        companionActive = adb.shell(serial, 5000, "settings get secure enabled_accessibility_services").text()
                .contains(companionPackage + "/");
        if (!companionActive) limitations.add("Companion AccessibilityService not enabled: ADB-only capture, "
                + "element metadata resolved from hierarchy snapshots with lower confidence; text input not captured.");
        correlator = new EventCorrelator(companionActive);
        clockOffsetMs = computeClockOffset();
        Map<String, int[]> touch = AdbParsers.parseTouchDevices(adb.shell(serial, 8000, "getevent -pl").text());
        int[] size = AdbParsers.parseWmSize(adb.shell(serial, 5000, "wm size").text());
        if (touch.isEmpty() || size == null) {
            limitations.add("No readable touchscreen via getevent; raw touch coordinates unavailable.");
        } else {
            int[] max = touch.values().iterator().next();
            mapper = new CoordinateMapper(max[0], max[1], size[0], size[1]);
        }
        Snapshot first = capturer.capture(screenshots, redact, keywords, null);
        upload(first);
        correlator.addReady(screenChange(first, "Initial screen at recording start."));
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("status", "RECORDING");
        state.put("packageName", first.packageName);
        state.put("limitations", new ArrayList<>(limitations));
        state.put("captureMode", Map.of("companionAccessibility", companionActive, "adbGetevent", mapper != null,
                "screenshots", screenshots, "redaction", redact));
        backend.sessionState(id, state);
        if (mapper != null) startGetevent(touch);
        if (companionActive) startLogcat();
        ticker.scheduleWithFixedDelay(this::tick, 200, 200, TimeUnit.MILLISECONDS);
        ticker.scheduleWithFixedDelay(this::uploadEvents, 500, 500, TimeUnit.MILLISECONDS);
        LOG.info("Recording " + id + " started on " + serial + " companion=" + companionActive + " getevent=" + (mapper != null));
    }

    public void pause() {
        paused = true;
        correlator.clear();
    }

    public void resume() {
        paused = false;
        captureRequestedAt = System.currentTimeMillis();
    }

    public void stop() throws Exception {
        stopped = true;
        streams.forEach(Process::destroy);
        ticker.shutdown();
        ticker.awaitTermination(3, TimeUnit.SECONDS);
        captureExec.shutdown();
        captureExec.awaitTermination(20, TimeUnit.SECONDS);
        if (!paused) process(correlator.flush(System.currentTimeMillis(), true));
        for (int i = 0; i < 20 && !outbox.isEmpty(); i++) uploadEvents();
        if (keyboardTouches.get() > 0) limitations.add(keyboardTouches.get() + " touches on the soft keyboard were "
                + "not recorded as TAP actions; typed text is captured via accessibility where permitted.");
        if (filteredByPackage.get() > 0) limitations.add(filteredByPackage.get() + " events outside package filter '"
                + packageFilter + "' were discarded.");
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("status", "COMPLETED");
        state.put("limitations", new ArrayList<>(limitations));
        backend.sessionState(id, state);
        LOG.info("Recording " + id + " completed; events=" + sequence.get());
    }

    public void abort(String reason) {
        stopped = true;
        streams.forEach(Process::destroy);
        ticker.shutdownNow();
        captureExec.shutdownNow();
        try {
            backend.sessionState(id, Map.of("status", "FAILED", "error", reason));
        } catch (Exception e) {
            LOG.warning("Could not report failure: " + e.getMessage());
        }
    }

    private long computeClockOffset() {
        try {
            long before = System.currentTimeMillis();
            String out = adb.shell(serial, 5000, "date +%s%3N").text().trim();
            long host = (before + System.currentTimeMillis()) / 2;
            if (out.matches("\\d{13}")) return host - Long.parseLong(out);
            String sec = adb.shell(serial, 5000, "date +%s").text().trim();
            limitations.add("Device clock has second precision; accessibility timestamps aligned within ~1s.");
            return host - Long.parseLong(sec) * 1000;
        } catch (Exception e) {
            limitations.add("Device clock offset unavailable; accessibility timestamps use device clock.");
            return 0;
        }
    }

    private void startGetevent(Map<String, int[]> touchDevices) throws Exception {
        GeteventParser parser = new GeteventParser(touchDevices.keySet(), new GeteventParser.Listener() {
            public void onTouch(GeteventParser.RawTouch t) {
                if (paused || stopped) return;
                int rot = currentRotation();
                int[] a = mapper.map(t.startX, t.startY, rot), b = mapper.map(t.endX, t.endY, rot);
                if (isKeyboardTouch(a[0], a[1])) {
                    keyboardTouches.incrementAndGet();
                    return;
                }
                correlator.onTouch(new TouchGesture(a[0], a[1], b[0], b[1], t.hostMs, t.durationMs, t.multiTouch));
            }

            public void onKey(String key, long hostMs) {
                if (!paused && !stopped) correlator.onKey(key, hostMs);
            }
        });
        Process p = adb.stream(serial, "shell", "getevent", "-lt");
        streams.add(p);
        readLines(p, "getevent", line -> parser.accept(line, System.currentTimeMillis()));
    }

    private void startLogcat() throws Exception {
        Process p = adb.stream(serial, "logcat", "-T", "1", "-v", "raw", "-s", COMPANION_TAG + ":I");
        streams.add(p);
        readLines(p, "logcat", line -> {
            if (paused || stopped) return;
            CompanionEvent e = CompanionEvent.parse(line, clockOffsetMs);
            if (e == null || e.ts < startedAtMs - 1000 || companionPackage.equals(e.pkg)) return;
            if ("IME".equals(e.type)) {
                imeBounds = e.imeBounds;
            } else if ("WINDOW_CHANGE".equals(e.type)) {
                captureRequestedAt = Math.min(captureRequestedAt, System.currentTimeMillis() + 500);
            } else {
                correlator.onCompanion(e);
            }
        });
    }

    private void readLines(Process p, String name, java.util.function.Consumer<String> consumer) {
        Thread t = new Thread(() -> {
            try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) consumer.accept(line);
            } catch (Exception e) {
                if (!stopped) LOG.warning(name + " stream ended: " + e.getMessage());
            }
            if (!stopped) limitations.add(name + " stream ended unexpectedly during recording.");
        }, name + "-" + serial);
        t.setDaemon(true);
        t.start();
    }

    private boolean isKeyboardTouch(int x, int y) {
        int[] b = imeBounds;
        if (b != null) return x >= b[0] && x < b[2] && y >= b[1] && y < b[3];
        if (!companionActive && imeShownFallback) {
            Snapshot s = latest();
            return s != null && s.height != null && y > s.height * 0.55;
        }
        return false;
    }

    private int currentRotation() {
        Snapshot s = latest();
        return s != null && s.orientation != null ? s.orientation : 0;
    }

    private Snapshot latest() {
        return snapshots.isEmpty() ? null : snapshots.get(snapshots.size() - 1);
    }

    private void tick() {
        try {
            long now = System.currentTimeMillis();
            if (!paused) process(correlator.flush(now, false));
            boolean due = now - lastCaptureMs >= captureIntervalMs || now >= captureRequestedAt;
            if (!paused && due && captureBusy.compareAndSet(false, true)) {
                captureRequestedAt = Long.MAX_VALUE;
                captureExec.submit(this::periodicCapture);
            }
        } catch (Exception e) {
            LOG.log(Level.WARNING, "tick failed", e);
        }
    }

    private void periodicCapture() {
        try {
            Snapshot prev = latest();
            Snapshot s = capturer.capture(screenshots, redact, keywords, prev == null ? null : prev.xml);
            lastCaptureMs = System.currentTimeMillis();
            if (!companionActive) imeShownFallback = AdbParsers.parseImeShown(
                    adb.shell(serial, 5000, "dumpsys input_method").text());
            if (s == null || paused || stopped) return;
            upload(s);
            boolean changed = prev == null || !s.structuralHash.equals(prev.structuralHash)
                    || (s.activity != null && !s.activity.equals(prev.activity));
            if (changed) correlator.addReady(screenChange(s, "Detected by hierarchy polling; actual transition may be earlier."));
        } catch (Exception e) {
            LOG.warning("capture failed: " + e.getMessage());
            lastCaptureMs = System.currentTimeMillis();
        } finally {
            captureBusy.set(false);
        }
    }

    private void upload(Snapshot s) throws Exception {
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("packageName", s.packageName);
        meta.put("activity", s.activity);
        meta.put("width", s.width);
        meta.put("height", s.height);
        meta.put("orientation", s.orientation);
        meta.put("capturedAt", s.capturedAtIso());
        meta.put("hierarchyHash", s.structuralHash);
        meta.put("screenshotStatus", s.screenshotStatus);
        meta.put("limitations", s.limitations);
        JsonNode r = backend.uploadScreen(id, meta, s.xml, s.screenshotPng);
        s.screenId = r.path("screenId").asText(null);
        s.hierarchyRef = r.path("hierarchyRef").asText(null);
        s.screenshotRef = r.path("screenshotRef").isNull() ? null : r.path("screenshotRef").asText(null);
        s.screenshotPng = null;
        snapshots.add(s);
    }

    private Map<String, Object> screenChange(Snapshot s, String note) {
        Map<String, Object> e = EventCorrelator.base("SCREEN_CHANGE", s.capturedAtMs, "ADB_UIAUTOMATOR", 0.9);
        e.put("packageName", s.packageName);
        EventCorrelator.limit(e, note);
        return e;
    }

    private Snapshot snapshotAt(long ts) {
        Snapshot best = null;
        for (Snapshot s : snapshots) if (s.capturedAtMs <= ts) best = s;
        return best;
    }

    @SuppressWarnings("unchecked")
    void process(List<Map<String, Object>> events) {
        for (Map<String, Object> e : events) {
            long ts = (Long) e.remove("_ts");
            Snapshot snap = snapshotAt(ts);
            boolean needsElement = e.remove(EventCorrelator.NEEDS_ELEMENT) != null;
            if (snap != null) {
                e.put("screenId", snap.screenId);
                e.put("hierarchyRef", snap.hierarchyRef);
                e.put("screenshotRef", snap.screenshotRef);
                e.put("activity", snap.activity);
                if (e.get("packageName") == null) e.put("packageName", snap.packageName);
            } else {
                e.put("screenId", null);
                e.put("hierarchyRef", null);
                e.put("screenshotRef", null);
                EventCorrelator.limit(e, "No hierarchy snapshot was available before this action.");
            }
            if (needsElement) resolveElement(e, snap);
            Object pkg = e.get("packageName");
            if (packageFilter != null && pkg != null && !packageFilter.equals(pkg)) {
                filteredByPackage.incrementAndGet();
                continue;
            }
            e.put("eventId", UUID.randomUUID().toString());
            e.put("sessionId", id);
            e.put("sequence", sequence.incrementAndGet());
            e.put("timestamp", Instant.ofEpochMilli(ts).toString());
            e.put("deviceId", serial);
            SensitiveMasker.apply(e, keywords);
            outbox.add(e);
            if (!"SCREEN_CHANGE".equals(e.get("action"))) {
                captureRequestedAt = Math.min(captureRequestedAt, System.currentTimeMillis() + 700);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private void resolveElement(Map<String, Object> e, Snapshot snap) {
        Map<String, Object> c = (Map<String, Object>) e.get("coordinates");
        HierarchyIndex.Node node = snap == null || c == null ? null
                : snap.index.findAt((Integer) c.get("x"), (Integer) c.get("y"));
        if (node != null) {
            e.put("element", node.toElement());
            EventCorrelator.limit(e, "Element resolved from the nearest hierarchy snapshot; may be stale.");
        } else {
            e.put("uncertain", true);
            e.put("confidence", 0.3);
            EventCorrelator.limit(e, "No UI element found at the touch coordinates (system UI, keyboard or stale snapshot).");
        }
    }

    private void uploadEvents() {
        List<Map<String, Object>> batch = new ArrayList<>();
        outbox.drainTo(batch, 200);
        if (batch.isEmpty()) return;
        try {
            JsonNode r = backend.events(id, batch);
            if (r.path("rejected").size() > 0) LOG.warning("Backend rejected events: " + r.get("rejected"));
        } catch (BackendClient.BackendException be) {
            LOG.warning("Events rejected (" + be.status + "): " + be.getMessage());
        } catch (Exception ex) {
            LOG.warning("Event upload failed, will retry: " + ex.getMessage());
            outbox.addAll(batch);
        }
    }
}
