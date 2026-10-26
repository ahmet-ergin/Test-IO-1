package com.amts.agent.events;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parses `adb shell getevent -lt` lines into raw single-finger touches and key presses.
 * Raw coordinates are in touch-panel units; {@link CoordinateMapper} converts them to screen pixels.
 */
public class GeteventParser {
    private static final Pattern LINE = Pattern.compile(
            "^\\[\\s*([\\d.]+)]\\s+(/dev/input/event\\d+):\\s+(\\S+)\\s+(\\S+)\\s+(\\S+)");

    public interface Listener {
        void onTouch(RawTouch touch);

        void onKey(String keyName, long hostMs);
    }

    public static final class RawTouch {
        public final int startX, startY, endX, endY;
        public final long hostMs, durationMs;
        public final boolean multiTouch;

        public RawTouch(int startX, int startY, int endX, int endY, long hostMs, long durationMs, boolean multiTouch) {
            this.startX = startX;
            this.startY = startY;
            this.endX = endX;
            this.endY = endY;
            this.hostMs = hostMs;
            this.durationMs = durationMs;
            this.multiTouch = multiTouch;
        }
    }

    private final java.util.Set<String> touchDevices;
    private final Listener listener;
    private int slot = 0;
    private int x = -1, y = -1, startX, startY;
    private boolean down, pendingDown, pendingUp, multi;
    private double downKernel;
    private long downHost;

    public GeteventParser(java.util.Set<String> touchDevices, Listener listener) {
        this.touchDevices = touchDevices;
        this.listener = listener;
    }

    public void accept(String line, long hostMs) {
        Matcher m = LINE.matcher(line);
        if (!m.find()) return;
        double kernel = Double.parseDouble(m.group(1));
        String dev = m.group(2), type = m.group(3), code = m.group(4), value = m.group(5);
        if ("EV_KEY".equals(type) && code.startsWith("KEY_")) {
            if ("UP".equals(value)) listener.onKey(code, hostMs);
            return;
        }
        if (!touchDevices.contains(dev)) return;
        switch (type) {
            case "EV_ABS":
                handleAbs(code, value);
                break;
            case "EV_KEY":
                if ("BTN_TOUCH".equals(code)) {
                    if ("DOWN".equals(value) && !down) pendingDown = true;
                    if ("UP".equals(value) && down) pendingUp = true;
                }
                break;
            case "EV_SYN":
                if ("SYN_REPORT".equals(code)) syn(kernel, hostMs);
                break;
            default:
                break;
        }
    }

    private void handleAbs(String code, String value) {
        switch (code) {
            case "ABS_MT_SLOT":
                slot = (int) Long.parseLong(value, 16);
                if (slot != 0 && down) multi = true;
                break;
            case "ABS_MT_TRACKING_ID":
                boolean release = "ffffffff".equalsIgnoreCase(value);
                if (slot == 0) {
                    if (release && down) pendingUp = true;
                    else if (!release && !down) pendingDown = true;
                } else if (!release) {
                    multi = true;
                }
                break;
            case "ABS_MT_POSITION_X":
                if (slot == 0) x = (int) Long.parseLong(value, 16);
                break;
            case "ABS_MT_POSITION_Y":
                if (slot == 0) y = (int) Long.parseLong(value, 16);
                break;
            default:
                break;
        }
    }

    private void syn(double kernel, long hostMs) {
        if (pendingDown && !down) {
            down = true;
            pendingDown = false;
            startX = x;
            startY = y;
            downKernel = kernel;
            downHost = hostMs;
        }
        if (pendingUp && down) {
            long duration = Math.max(0, Math.round((kernel - downKernel) * 1000));
            listener.onTouch(new RawTouch(startX, startY, x, y, downHost, duration, multi));
            down = false;
            pendingUp = false;
            multi = false;
        }
    }
}
