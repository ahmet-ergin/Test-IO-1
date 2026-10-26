package com.amts.agent.events;

/** A touch converted to screen pixels and classified. */
public class TouchGesture {
    public static final int TOUCH_SLOP_PX = 40;
    public static final long LONG_PRESS_MS = 500;

    public final String action;
    public final int x1, y1, x2, y2;
    public final long ts, durationMs;
    public final boolean multiTouch;

    public TouchGesture(int x1, int y1, int x2, int y2, long ts, long durationMs, boolean multiTouch) {
        this.x1 = x1;
        this.y1 = y1;
        this.x2 = x2;
        this.y2 = y2;
        this.ts = ts;
        this.durationMs = durationMs;
        this.multiTouch = multiTouch;
        double dist = Math.hypot(x2 - x1, y2 - y1);
        if (dist > TOUCH_SLOP_PX) action = "SWIPE";
        else action = durationMs >= LONG_PRESS_MS ? "LONG_PRESS" : "TAP";
    }
}
