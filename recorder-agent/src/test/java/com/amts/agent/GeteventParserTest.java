package com.amts.agent;

import com.amts.agent.events.CoordinateMapper;
import com.amts.agent.events.GeteventParser;
import com.amts.agent.events.TouchGesture;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class GeteventParserTest {
    private final List<GeteventParser.RawTouch> touches = new ArrayList<>();
    private final List<String> keys = new ArrayList<>();
    private final GeteventParser parser = new GeteventParser(Set.of("/dev/input/event2"), new GeteventParser.Listener() {
        public void onTouch(GeteventParser.RawTouch t) {
            touches.add(t);
        }

        public void onKey(String k, long ms) {
            keys.add(k);
        }
    });

    private void feed(String... lines) {
        for (String l : lines) parser.accept(l, 1000);
    }

    private static String l(String ts, String type, String code, String val) {
        return "[" + ts + "] /dev/input/event2: " + type + " " + code + " " + val;
    }

    @Test
    void parsesSingleTap() {
        feed(l("  100.000000", "EV_ABS", "ABS_MT_TRACKING_ID", "00000012"),
                l("  100.000000", "EV_ABS", "ABS_MT_POSITION_X", "000001f4"),
                l("  100.000000", "EV_ABS", "ABS_MT_POSITION_Y", "000003e8"),
                l("  100.000000", "EV_KEY", "BTN_TOUCH", "DOWN"),
                l("  100.000000", "EV_SYN", "SYN_REPORT", "00000000"),
                l("  100.080000", "EV_ABS", "ABS_MT_TRACKING_ID", "ffffffff"),
                l("  100.080000", "EV_KEY", "BTN_TOUCH", "UP"),
                l("  100.080000", "EV_SYN", "SYN_REPORT", "00000000"));
        assertEquals(1, touches.size());
        GeteventParser.RawTouch t = touches.get(0);
        assertEquals(500, t.startX);
        assertEquals(1000, t.startY);
        assertEquals(80, t.durationMs);
        assertFalse(t.multiTouch);
        assertEquals("TAP", new TouchGesture(t.startX, t.startY, t.endX, t.endY, 0, t.durationMs, false).action);
    }

    @Test
    void parsesSwipeAndLongPress() {
        feed(l("1.0", "EV_ABS", "ABS_MT_TRACKING_ID", "1"), l("1.0", "EV_ABS", "ABS_MT_POSITION_X", "100"),
                l("1.0", "EV_ABS", "ABS_MT_POSITION_Y", "800"), l("1.0", "EV_SYN", "SYN_REPORT", "0"),
                l("1.2", "EV_ABS", "ABS_MT_POSITION_Y", "200"), l("1.2", "EV_SYN", "SYN_REPORT", "0"),
                l("1.3", "EV_ABS", "ABS_MT_TRACKING_ID", "ffffffff"), l("1.3", "EV_SYN", "SYN_REPORT", "0"));
        GeteventParser.RawTouch s = touches.get(0);
        assertEquals("SWIPE", new TouchGesture(s.startX, s.startY, s.endX, s.endY, 0, s.durationMs, false).action);
        assertEquals(0x200, s.endY);
        assertEquals("LONG_PRESS", new TouchGesture(10, 10, 12, 12, 0, 900, false).action);
    }

    @Test
    void flagsMultiTouchAndIgnoresOtherDevices() {
        feed(l("2.0", "EV_ABS", "ABS_MT_TRACKING_ID", "5"), l("2.0", "EV_ABS", "ABS_MT_POSITION_X", "10"),
                l("2.0", "EV_ABS", "ABS_MT_POSITION_Y", "10"), l("2.0", "EV_SYN", "SYN_REPORT", "0"),
                l("2.1", "EV_ABS", "ABS_MT_SLOT", "1"), l("2.1", "EV_ABS", "ABS_MT_TRACKING_ID", "6"),
                l("2.1", "EV_SYN", "SYN_REPORT", "0"), l("2.2", "EV_ABS", "ABS_MT_SLOT", "0"),
                l("2.2", "EV_ABS", "ABS_MT_TRACKING_ID", "ffffffff"), l("2.2", "EV_SYN", "SYN_REPORT", "0"));
        assertTrue(touches.get(0).multiTouch);
        parser.accept("[3.0] /dev/input/event9: EV_ABS ABS_MT_TRACKING_ID 00000001", 0);
        parser.accept("[3.0] /dev/input/event9: EV_SYN SYN_REPORT 00000000", 0);
        assertEquals(1, touches.size());
    }

    @Test
    void reportsKeysOnRelease() {
        parser.accept("[5.0] /dev/input/event1: EV_KEY KEY_BACK DOWN", 0);
        parser.accept("[5.1] /dev/input/event1: EV_KEY KEY_BACK UP", 0);
        assertEquals(List.of("KEY_BACK"), keys);
    }

    @Test
    void mapsCoordinatesWithRotation() {
        CoordinateMapper m = new CoordinateMapper(4095, 4095, 1080, 2400);
        assertArrayEquals(new int[]{540, 1200}, m.map(2048, 2048, 0));
        int[] r = m.map(0, 0, 1);
        assertArrayEquals(new int[]{0, 1080}, r);
    }
}
