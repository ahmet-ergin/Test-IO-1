package com.amts.agent.events;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Event emitted by the Android companion AccessibilityService via logcat tag AMTS_EVT.
 * Contract (v1): {"v":1,"type":"CLICK|LONG_CLICK|TEXT_CHANGED|SCROLL|WINDOW_CHANGE|IME","ts":epochMs,
 * "pkg":..,"cls":..,"node":{...},"textValue":..,"textLength":..,"masked":bool,"imeBounds":[l,t,r,b]}
 */
public class CompanionEvent {
    private static final ObjectMapper JSON = new ObjectMapper();

    public String type;
    public long ts;
    public String pkg;
    public String cls;
    public Map<String, Object> node;
    public String textValue;
    public Integer textLength;
    public boolean masked;
    public int[] imeBounds;

    public static CompanionEvent parse(String line, long clockOffsetMs) {
        int idx = line.indexOf('{');
        if (idx < 0) return null;
        try {
            JsonNode j = JSON.readTree(line.substring(idx));
            if (j.path("v").asInt() != 1) return null;
            CompanionEvent e = new CompanionEvent();
            e.type = j.path("type").asText();
            e.ts = j.path("ts").asLong() + clockOffsetMs;
            e.pkg = text(j, "pkg");
            e.cls = text(j, "cls");
            e.textValue = text(j, "textValue");
            e.textLength = j.hasNonNull("textLength") ? j.get("textLength").asInt() : null;
            e.masked = j.path("masked").asBoolean(false);
            if (j.has("imeBounds") && j.get("imeBounds").isArray() && j.get("imeBounds").size() == 4) {
                JsonNode b = j.get("imeBounds");
                e.imeBounds = new int[]{b.get(0).asInt(), b.get(1).asInt(), b.get(2).asInt(), b.get(3).asInt()};
            }
            if (j.hasNonNull("node")) e.node = toElement(j.get("node"));
            return e;
        } catch (Exception ex) {
            return null;
        }
    }

    private static Map<String, Object> toElement(JsonNode n) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("resourceId", text(n, "resourceId"));
        e.put("accessibilityId", text(n, "contentDesc"));
        e.put("text", text(n, "text"));
        e.put("contentDesc", text(n, "contentDesc"));
        e.put("hint", text(n, "hint"));
        e.put("className", text(n, "className"));
        List<Integer> bounds = null;
        if (n.has("bounds") && n.get("bounds").isArray() && n.get("bounds").size() == 4) {
            bounds = new ArrayList<>();
            for (JsonNode b : n.get("bounds")) bounds.add(b.asInt());
        }
        e.put("bounds", bounds);
        e.put("clickable", n.hasNonNull("clickable") ? n.get("clickable").asBoolean() : null);
        e.put("enabled", n.hasNonNull("enabled") ? n.get("enabled").asBoolean() : null);
        e.put("password", n.hasNonNull("password") ? n.get("password").asBoolean() : null);
        e.put("resolvedFrom", "ACCESSIBILITY_NODE");
        return e;
    }

    private static String text(JsonNode j, String k) {
        return j.hasNonNull(k) && !j.get(k).asText().isEmpty() ? j.get(k).asText() : null;
    }

    public String nodeKey() {
        if (node == null) return "?";
        Object rid = node.get("resourceId");
        return rid != null ? rid.toString() : String.valueOf(node.get("bounds"));
    }

    @SuppressWarnings("unchecked")
    public boolean contains(int x, int y) {
        if (node == null || node.get("bounds") == null) return true;
        List<Integer> b = (List<Integer>) node.get("bounds");
        return x >= b.get(0) && x < b.get(2) && y >= b.get(1) && y < b.get(3);
    }
}
