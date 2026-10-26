import { useApp } from "@/context/AppContext";
import { Tag, EmptyState } from "@/components/common";

export const elementLabel = (e) => {
  const el = e?.element;
  if (!el) return e?.coordinates ? `(${e.coordinates.x}, ${e.coordinates.y})` : null;
  return el.text || el.contentDesc || el.resourceId?.split("/").pop() || el.className?.split(".").pop() || null;
};

const FeedRow = ({ e, onSelect, selected }) => {
  const { t } = useApp();
  return (
    <button onClick={() => onSelect?.(e)} data-testid={`feed-event-${e.sequence}`}
      className={`feed-row flex w-full items-center gap-3 border-b border-border px-3 py-2 text-left text-xs transition-colors hover:bg-muted/50 ${selected ? "bg-primary/5" : ""}`}>
      <span className="w-8 shrink-0 font-mono text-muted-foreground">#{e.sequence}</span>
      <span className="w-24 shrink-0 font-mono font-semibold">{e.action}</span>
      <span className="min-w-0 flex-1 truncate">{elementLabel(e) || <span className="text-muted-foreground">{t("unavailable")}</span>}
        {e.inputValue && <span className="ml-2 font-mono text-muted-foreground">= {e.inputValue.masked ? `[${t("masked")} · ${e.inputValue.length ?? "?"}]` : `"${e.inputValue.value}"`}</span>}
      </span>
      {e.uncertain && <Tag tone="amber">{t("uncertain")}</Tag>}
      <Tag tone={e.captureSource === "HYBRID" ? "green" : e.captureSource === "DEMO" ? "amber" : "blue"}>{e.captureSource}</Tag>
      <span className="w-20 shrink-0 text-right font-mono text-muted-foreground">{new Date(e.timestamp).toLocaleTimeString()}</span>
    </button>
  );
};

export const EventFeed = ({ events, onSelect, selectedId, testId = "live-event-feed" }) => {
  const { t } = useApp();
  if (!events.length) return <EmptyState text={t("rec_no_events")} testId={`${testId}-empty`} />;
  return (
    <div data-testid={testId} className="max-h-[460px] overflow-y-auto rounded border border-border">
      {[...events].reverse().map((e) => <FeedRow key={e.eventId} e={e} onSelect={onSelect} selected={selectedId === e.eventId} />)}
    </div>
  );
};
