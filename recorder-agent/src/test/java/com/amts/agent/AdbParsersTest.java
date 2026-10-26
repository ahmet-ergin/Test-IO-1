package com.amts.agent;

import com.amts.agent.adb.AdbParsers;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class AdbParsersTest {
    @Test
    void parsesDevicesList() {
        String out = "List of devices attached\n"
                + "R58M12345   device usb:1-1 product:beyond1 model:SM_G973F device:beyond1 transport_id:2\n"
                + "emulator-5554 unauthorized transport_id:3\n"
                + "192.168.1.5:5555 offline\n\n";
        List<AdbParsers.DeviceLine> d = AdbParsers.parseDevices(out);
        assertEquals(3, d.size());
        assertEquals("R58M12345", d.get(0).serial);
        assertEquals("device", d.get(0).state);
        assertEquals("SM_G973F", d.get(0).attrs.get("model"));
        assertEquals("unauthorized", d.get(1).state);
        assertEquals("offline", d.get(2).state);
    }

    @Test
    void parsesEmptyDeviceList() {
        assertTrue(AdbParsers.parseDevices("List of devices attached\n\n").isEmpty());
        assertTrue(AdbParsers.parseDevices("* daemon started successfully\nList of devices attached\n").isEmpty());
    }

    @Test
    void parsesWmSizePreferringOverride() {
        assertArrayEquals(new int[]{1080, 2400}, AdbParsers.parseWmSize("Physical size: 1080x2400\n"));
        assertArrayEquals(new int[]{720, 1600},
                AdbParsers.parseWmSize("Physical size: 1080x2400\nOverride size: 720x1600\n"));
        assertNull(AdbParsers.parseWmSize("error"));
    }

    @Test
    void parsesFocusedWindow() {
        String[] f = AdbParsers.parseFocusedWindow(
                "  mCurrentFocus=Window{a1b2c3 u0 com.example.bank/com.example.bank.ui.LoginActivity}\n");
        assertArrayEquals(new String[]{"com.example.bank", "com.example.bank.ui.LoginActivity"}, f);
        String[] rel = AdbParsers.parseFocusedWindow(
                "mFocusedApp=ActivityRecord{77 u0 com.example.bank/.MainActivity t12}");
        assertEquals("com.example.bank.MainActivity", rel[1]);
        assertNull(AdbParsers.parseFocusedWindow("nothing"));
    }

    @Test
    void parsesOrientationAndIme() {
        assertEquals(1, AdbParsers.parseOrientation("    SurfaceOrientation: 1\n"));
        assertNull(AdbParsers.parseOrientation(""));
        assertTrue(AdbParsers.parseImeShown("  mInputShown=true"));
        assertFalse(AdbParsers.parseImeShown("  mInputShown=false"));
    }

    @Test
    void parsesTouchDevices() {
        String out = "add device 1: /dev/input/event3\n  name: \"gpio-keys\"\n  events:\n    KEY (0001): KEY_VOLUMEDOWN\n"
                + "add device 2: /dev/input/event2\n  name: \"sec_touchscreen\"\n  events:\n"
                + "    ABS (0003): ABS_MT_SLOT           : value 0, min 0, max 9, fuzz 0, flat 0, resolution 0\n"
                + "                ABS_MT_POSITION_X     : value 0, min 0, max 4095, fuzz 0, flat 0, resolution 0\n"
                + "                ABS_MT_POSITION_Y     : value 0, min 0, max 4095, fuzz 0, flat 0, resolution 0\n";
        Map<String, int[]> t = AdbParsers.parseTouchDevices(out);
        assertEquals(1, t.size());
        assertArrayEquals(new int[]{4095, 4095}, t.get("/dev/input/event2"));
    }

    @Test
    void parsesAdbVersion() {
        assertEquals("1.0.41 (35.0.1-11580240)",
                AdbParsers.parseAdbVersion("Android Debug Bridge version 1.0.41\nVersion 35.0.1-11580240\n"));
    }
}
