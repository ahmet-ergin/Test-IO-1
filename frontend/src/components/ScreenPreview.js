import { useEffect, useRef, useState } from "react";
import { useApp } from "@/context/AppContext";
import { artifactUrl, http } from "@/lib/api";
import { Tag } from "@/components/common";

/** Screenshot with the element bounds of the highlighted event drawn on top. */
export const ScreenPreview = ({ screen, highlight, testId = "screen-preview" }) => {
  const { t } = useApp();
  const imgRef = useRef(null);
  const [scale, setScale] = useState(null);
  const src = artifactUrl(screen?.screenshotRef);
  const onLoad = () => {
    const img = imgRef.current;
    if (img && screen?.width) setScale(img.clientWidth / screen.width);
  };
  useEffect(() => { setScale(null); }, [src]);
  const b = highlight?.element?.bounds;
  const pt = highlight?.coordinates;
  return (
    <div data-testid={testId} className="space-y-2">
      <div className="grid-bg relative mx-auto flex min-h-[260px] w-full max-w-[300px] items-center justify-center overflow-hidden rounded-md border border-border bg-muted/30">
        {src ? (
          <div className="relative">
            <img ref={imgRef} src={src} alt="captured screen" onLoad={onLoad} className="block max-h-[520px] w-auto" data-testid={`${testId}-image`} />
            {scale && b && (
              <div className="pointer-events-none absolute border-2 border-primary bg-primary/10"
                style={{ left: b[0] * scale, top: b[1] * scale, width: (b[2] - b[0]) * scale, height: (b[3] - b[1]) * scale }} />
            )}
            {scale && pt && (
              <div className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-red-500 bg-red-500/40"
                style={{ left: pt.x * scale, top: pt.y * scale }} />
            )}
          </div>
        ) : (
          <p className="px-6 text-center text-xs text-muted-foreground">
            {screen ? `${t("rec_screenshot_status")}: ${screen.screenshotStatus || t("unavailable")}` : t("rec_no_screen")}
          </p>
        )}
      </div>
      {screen && (
        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
          <Tag>{screen.screenName}</Tag>
          {screen.width && <span>{screen.width}×{screen.height}</span>}
          {screen.orientation != null && <span>rot {screen.orientation}</span>}
          {screen.screenshotStatus && <Tag tone={screen.screenshotStatus === "BLOCKED_SECURE" ? "amber" : "muted"}>{screen.screenshotStatus}</Tag>}
        </div>
      )}
    </div>
  );
};

export const useScreen = (screenId, sessionId) => {
  const [screen, setScreen] = useState(null);
  useEffect(() => {
    if (!screenId || !sessionId) { setScreen(null); return; }
    http.get(`/sessions/${sessionId}/screens`).then((r) => setScreen(r.data.find((s) => s.id === screenId) || null)).catch(() => {});
  }, [screenId, sessionId]);
  return screen;
};
