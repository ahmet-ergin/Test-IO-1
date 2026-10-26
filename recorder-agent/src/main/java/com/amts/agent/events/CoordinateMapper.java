package com.amts.agent.events;

/** Converts raw touch-panel coordinates (natural orientation) into current-rotation screen pixels. */
public class CoordinateMapper {
    private final int maxX, maxY, naturalW, naturalH;

    public CoordinateMapper(int maxX, int maxY, int naturalW, int naturalH) {
        this.maxX = maxX;
        this.maxY = maxY;
        this.naturalW = naturalW;
        this.naturalH = naturalH;
    }

    /** rotation: 0,1,2,3 = 0/90/180/270 degrees. */
    public int[] map(int rawX, int rawY, int rotation) {
        int nx = (int) Math.round(rawX * (naturalW / (double) (maxX + 1)));
        int ny = (int) Math.round(rawY * (naturalH / (double) (maxY + 1)));
        switch (rotation) {
            case 1:
                return new int[]{ny, naturalW - nx};
            case 2:
                return new int[]{naturalW - nx, naturalH - ny};
            case 3:
                return new int[]{naturalH - ny, nx};
            default:
                return new int[]{nx, ny};
        }
    }
}
