package com.amts.agent;

import com.amts.agent.capture.HierarchyIndex;
import com.amts.agent.events.CompanionEvent;
import com.amts.agent.events.EventCorrelator;
import com.amts.agent.events.SensitiveMasker;
import com.amts.agent.events.TouchGesture;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class CorrelatorAndMaskingTest {
    private static final List<String> KW = List.of("password", "pin", "otp", "şifre");

    private static CompanionEvent click(long ts, String rid, int[] b) {
        String json = String.format("{\"v\":1,\"type\":\"CLICK\",\"ts\":%d,\"pkg\":\"com.bank\",\"node\":{\"resourceId\":\"%s\","
                + "\"text\":\"Transfer\",\"className\":\"android.widget.Button\",\"bounds\":[%d,%d,%d,%d]}}", ts, rid, b[0], b[1], b[2], b[3]);
        return CompanionEvent.parse("AMTS_EVT: " + json, 0);
    }

    @Test
    void mergesTouchWithAccessibilityClick() {
        EventCorrelator c = new EventCorrelator(true);
        c.onCompanion(click(1100, "com.bank:id/transfer", new int[]{100, 200, 350, 260}));
        c.onTouch(new TouchGesture(150, 230, 151, 231, 1000, 60, false));
        List<Map<String, Object>> out = c.flush(1200, false);
        assertEquals(1, out.size());
        Map<String, Object> e = out.get(0);
        assertEquals("TAP", e.get("action"));
        assertEquals("HYBRID", e.get("captureSource"));
        assertEquals(Map.of("x", 150, "y", 230), e.get("coordinates"));
    }

    @Test
    void unmatchedTouchWaitsWindowThenNeedsElement() {
        EventCorrelator c = new EventCorrelator(true);
        c.onTouch(new TouchGesture(10, 10, 10, 10, 1000, 50, false));
        assertTrue(c.flush(1500, false).isEmpty());
        Map<String, Object> e = c.flush(1900, false).get(0);
        assertEquals("ADB_GETEVENT", e.get("captureSource"));
        assertEquals(true, e.get(EventCorrelator.NEEDS_ELEMENT));
    }

    @Test
    void touchOutsideBoundsIsNotMerged() {
        EventCorrelator c = new EventCorrelator(true);
        c.onCompanion(click(1000, "com.bank:id/a", new int[]{0, 0, 10, 10}));
        c.onTouch(new TouchGesture(500, 500, 500, 500, 1000, 50, false));
        List<Map<String, Object>> out = c.flush(5000, false);
        assertEquals(2, out.size());
        assertEquals("ACCESSIBILITY", out.get(0).get("captureSource"));
    }

    @Test
    void aggregatesTextAndMasksPassword() {
        EventCorrelator c = new EventCorrelator(true);
        for (int i = 1; i <= 4; i++) {
            c.onCompanion(CompanionEvent.parse("{\"v\":1,\"type\":\"TEXT_CHANGED\",\"ts\":" + (1000 + i * 100)
                    + ",\"pkg\":\"com.bank\",\"textValue\":null,\"textLength\":" + i + ",\"masked\":true,"
                    + "\"node\":{\"resourceId\":\"com.bank:id/pwd\",\"password\":true}}", 0));
        }
        assertTrue(c.flush(1500, false).isEmpty());
        List<Map<String, Object>> out = c.flush(4000, false);
        assertEquals(1, out.size());
        @SuppressWarnings("unchecked") Map<String, Object> in = (Map<String, Object>) out.get(0).get("inputValue");
        assertEquals(true, in.get("masked"));
        assertNull(in.get("value"));
        assertEquals(4, in.get("length"));
    }

    @Test
    void textFinalizedWhenNextActionArrivesAndOrderPreserved() {
        EventCorrelator c = new EventCorrelator(true);
        c.onCompanion(CompanionEvent.parse("{\"v\":1,\"type\":\"TEXT_CHANGED\",\"ts\":1000,\"textValue\":\"Ali\","
                + "\"textLength\":3,\"node\":{\"resourceId\":\"com.bank:id/name\"}}", 0));
        c.onTouch(new TouchGesture(5, 5, 5, 5, 1200, 40, false));
        List<Map<String, Object>> out = c.flush(2100, false);
        assertEquals("INPUT_TEXT", out.get(0).get("action"));
        assertEquals("TAP", out.get(1).get("action"));
    }

    @Test
    void backKeyRecorded() {
        EventCorrelator c = new EventCorrelator(false);
        c.onKey("KEY_BACK", 10);
        c.onKey("KEY_VOLUMEUP", 11);
        List<Map<String, Object>> out = c.flush(20, false);
        assertEquals(1, out.size());
        assertEquals("BACK", out.get(0).get("action"));
    }

    @Test
    void maskerMasksSensitiveAndOtp() {
        Map<String, Object> el = new HashMap<>();
        el.put("resourceId", "com.bank:id/sifreInput");
        el.put("text", "visible");
        Map<String, Object> ev = new LinkedHashMap<>();
        ev.put("element", el);
        ev.put("inputValue", new HashMap<>(Map.of("masked", false, "value", "abc")));
        SensitiveMasker.apply(ev, KW);
        assertEquals(SensitiveMasker.MASK, el.get("text"));
        assertEquals(true, ((Map<?, ?>) ev.get("inputValue")).get("masked"));

        Map<String, Object> otp = new LinkedHashMap<>();
        otp.put("element", new HashMap<>(Map.of("resourceId", "com.bank:id/code")));
        otp.put("inputValue", new HashMap<>(Map.of("masked", false, "value", "123456")));
        SensitiveMasker.apply(otp, KW);
        assertEquals("OTP_PATTERN", ((Map<?, ?>) otp.get("inputValue")).get("reason"));
    }

    @Test
    void hierarchyFindsSmallestClickable() throws Exception {
        String xml = "<?xml version='1.0'?><hierarchy rotation=\"0\"><node class=\"android.widget.FrameLayout\" "
                + "package=\"com.bank\" bounds=\"[0,0][1080,2400]\" clickable=\"false\">"
                + "<node class=\"android.widget.LinearLayout\" clickable=\"true\" bounds=\"[0,100][1080,600]\">"
                + "<node class=\"android.widget.Button\" resource-id=\"com.bank:id/ok\" text=\"OK\" clickable=\"true\" "
                + "bounds=\"[100,200][300,260]\"/></node></node></hierarchy>";
        HierarchyIndex idx = new HierarchyIndex(xml);
        assertEquals("com.bank", idx.rootPackage);
        assertEquals("com.bank:id/ok", idx.findAt(150, 230).attrs.get("resource-id"));
        assertEquals("android.widget.LinearLayout", idx.findAt(900, 500).attrs.get("class"));
        assertNull(idx.findAt(5000, 5000));
        String typed = xml.replace("text=\"OK\"", "text=\"OK!\"");
        assertEquals(idx.structuralHash(), new HierarchyIndex(typed).structuralHash());
    }

    @Test
    void companionParserRejectsGarbage() {
        assertNull(CompanionEvent.parse("random log line", 0));
        assertNull(CompanionEvent.parse("{\"v\":2,\"type\":\"CLICK\"}", 0));
    }
}
