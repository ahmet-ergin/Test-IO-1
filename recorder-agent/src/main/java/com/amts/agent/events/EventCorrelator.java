package com.amts.agent.events;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Correlates ADB getevent touches with companion accessibility events.
 * Emits only what was observed; unresolved actions are marked uncertain rather than invented.
 * Not thread-safe: callers synchronize.
 */
public class EventCorrelator {
    public static final long MATCH_WINDOW_MS = 800;
    public static final long TEXT_IDLE_MS = 1500;
    public static final long SCROLL_MERGE_MS = 600;
    public static final String NEEDS_ELEMENT = "_needsElementResolution";

    private final List<TouchGesture> touches = new ArrayList<>();
    private final List<CompanionEvent> companion = new ArrayList<>();
    private final Map<String, TextAgg> texts = new LinkedHashMap<>();
    private final List<Map<String, Object>> ready = new ArrayList<>();
    private final boolean companionActive;

    private final List<TextAgg> doneTexts = new ArrayList<>();

    private static final class TextAgg {
        CompanionEvent first, last;
        long lastTs;
    }

    private static final class ScrollAgg {
        long lastTs;
    }

    private final Map<CompanionEvent, ScrollAgg> scrolls = new LinkedHashMap<>();

    public EventCorrelator(boolean companionActive) {
        this.companionActive = companionActive;
    }

    public synchronized void onTouch(TouchGesture g) {
        finalizeTexts();
        touches.add(g);
    }

    public synchronized void onKey(String key, long ts) {
        if ("KEY_BACK".equals(key)) {
            finalizeTexts();
            Map<String, Object> e = base("BACK", ts, "ADB_GETEVENT", 0.9);
            e.put("keyCode", key);
            ready.add(e);
        } else if (key.equals("KEY_ENTER") || key.equals("KEY_TAB") || key.equals("KEY_SEARCH")) {
            Map<String, Object> e = base("KEYBOARD_ACTION", ts, "ADB_GETEVENT", 0.8);
            e.put("keyCode", key);
            limit(e, "Hardware key only; soft-keyboard IME actions are not observable.");
            ready.add(e);
        }
    }

    public synchronized void onCompanion(CompanionEvent c) {
        switch (c.type) {
            case "CLICK":
            case "LONG_CLICK":
                finalizeTexts();
                companion.add(c);
                break;
            case "SCROLL":
                for (Map.Entry<CompanionEvent, ScrollAgg> s : scrolls.entrySet()) {
                    if (s.getKey().nodeKey().equals(c.nodeKey()) && c.ts - s.getValue().lastTs < SCROLL_MERGE_MS) {
                        s.getValue().lastTs = c.ts;
                        return;
                    }
                }
                ScrollAgg agg = new ScrollAgg();
                agg.lastTs = c.ts;
                scrolls.put(c, agg);
                companion.add(c);
                break;
            case "TEXT_CHANGED":
                TextAgg t = texts.get(c.nodeKey());
                if (t == null) {
                    t = new TextAgg();
                    t.first = c;
                    texts.put(c.nodeKey(), t);
                }
                t.last = c;
                t.lastTs = c.ts;
                break;
            default:
                break;
        }
    }

    public synchronized void addReady(Map<String, Object> event) {
        ready.add(event);
    }

    private void finalizeTexts() {
        doneTexts.addAll(texts.values());
        texts.clear();
    }

    public synchronized List<Map<String, Object>> flush(long now, boolean force) {
        matchPairs();
        for (Iterator<CompanionEvent> it = companion.iterator(); it.hasNext(); ) {
            CompanionEvent c = it.next();
            long lastTs = scrolls.containsKey(c) ? scrolls.get(c).lastTs : c.ts;
            if (force || now - lastTs >= MATCH_WINDOW_MS) {
                ready.add(fromCompanionOnly(c));
                scrolls.remove(c);
                it.remove();
            }
        }
        for (Iterator<TouchGesture> it = touches.iterator(); it.hasNext(); ) {
            TouchGesture g = it.next();
            if (force || now - g.ts >= MATCH_WINDOW_MS) {
                ready.add(fromTouchOnly(g));
                it.remove();
            }
        }
        for (Iterator<TextAgg> it = texts.values().iterator(); it.hasNext(); ) {
            TextAgg t = it.next();
            if (force || now - t.lastTs >= TEXT_IDLE_MS) {
                doneTexts.add(t);
                it.remove();
            }
        }
        for (TextAgg t : doneTexts) ready.add(fromText(t));
        doneTexts.clear();
        ready.sort(Comparator.comparingLong(e -> (Long) e.get("_ts")));
        List<Map<String, Object>> out = new ArrayList<>(ready);
        ready.clear();
        return out;
    }

    public synchronized void clear() {
        touches.clear();
        companion.clear();
        texts.clear();
        doneTexts.clear();
        scrolls.clear();
        ready.clear();
    }

    private void matchPairs() {
        for (Iterator<CompanionEvent> it = companion.iterator(); it.hasNext(); ) {
            CompanionEvent c = it.next();
            TouchGesture best = null;
            for (TouchGesture g : touches) {
                boolean compatible = c.type.equals("SCROLL") ? g.action.equals("SWIPE") : !g.action.equals("SWIPE");
                if (compatible && Math.abs(g.ts - c.ts) <= MATCH_WINDOW_MS && c.contains(g.x1, g.y1)
                        && (best == null || Math.abs(g.ts - c.ts) < Math.abs(best.ts - c.ts))) {
                    best = g;
                }
            }
            if (best != null) {
                touches.remove(best);
                scrolls.remove(c);
                it.remove();
                ready.add(merged(c, best));
            }
        }
    }

    private Map<String, Object> merged(CompanionEvent c, TouchGesture g) {
        String action = c.type.equals("SCROLL") ? "SCROLL" : (c.type.equals("LONG_CLICK") ? "LONG_PRESS" : g.action);
        Map<String, Object> e = base(action, g.ts, "HYBRID", 0.95);
        e.put("element", c.node);
        e.put("packageName", c.pkg);
        putCoords(e, g, !action.equals("TAP") && !action.equals("LONG_PRESS"));
        if (g.multiTouch) limit(e, "Multi-touch detected; only the first pointer was recorded.");
        return e;
    }

    private Map<String, Object> fromCompanionOnly(CompanionEvent c) {
        String action = c.type.equals("SCROLL") ? "SCROLL" : (c.type.equals("LONG_CLICK") ? "LONG_PRESS" : "TAP");
        Map<String, Object> e = base(action, c.ts, "ACCESSIBILITY", 0.85);
        e.put("element", c.node);
        e.put("packageName", c.pkg);
        limit(e, "No matching raw touch observed; coordinates unavailable.");
        return e;
    }

    private Map<String, Object> fromTouchOnly(TouchGesture g) {
        Map<String, Object> e = base(g.action, g.ts, "ADB_GETEVENT", g.action.equals("SWIPE") ? 0.7 : 0.6);
        putCoords(e, g, g.action.equals("SWIPE"));
        if (!g.action.equals("SWIPE")) e.put(NEEDS_ELEMENT, true);
        if (companionActive) limit(e, "Accessibility service reported no matching event for this touch.");
        if (g.multiTouch) limit(e, "Multi-touch detected; only the first pointer was recorded.");
        return e;
    }

    private Map<String, Object> fromText(TextAgg t) {
        CompanionEvent c = t.last;
        Map<String, Object> e = base("INPUT_TEXT", t.first.ts, "ACCESSIBILITY", 0.9);
        e.put("element", c.node);
        e.put("packageName", c.pkg);
        Map<String, Object> input = new LinkedHashMap<>();
        boolean masked = c.masked || c.textValue == null;
        input.put("masked", masked);
        input.put("value", masked ? null : c.textValue);
        input.put("length", c.textLength);
        input.put("reason", c.masked ? "PASSWORD_FIELD" : (c.textValue == null ? "VALUE_UNAVAILABLE" : null));
        e.put("inputValue", input);
        return e;
    }

    private static void putCoords(Map<String, Object> e, TouchGesture g, boolean withEnd) {
        e.put("coordinates", Map.of("x", g.x1, "y", g.y1));
        e.put("durationMs", g.durationMs);
        if (withEnd) e.put("endCoordinates", Map.of("x", g.x2, "y", g.y2));
    }

    public static Map<String, Object> base(String action, long ts, String source, double confidence) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("_ts", ts);
        e.put("action", action);
        e.put("captureSource", source);
        e.put("confidence", confidence);
        e.put("uncertain", false);
        e.put("element", null);
        e.put("coordinates", null);
        e.put("limitations", new ArrayList<String>());
        return e;
    }

    @SuppressWarnings("unchecked")
    public static void limit(Map<String, Object> e, String text) {
        ((List<String>) e.get("limitations")).add(text);
    }
}
