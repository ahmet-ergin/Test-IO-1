import { AlertTriangle, CircleDot, Terminal } from "lucide-react";
import { useApp } from "@/context/AppContext";

const STATUS_STYLES = {
  IDLE: "bg-muted text-muted-foreground border-border",
  STARTING: "bg-sky-500/10 text-sky-500 border-sky-500/30",
  RECORDING: "bg-red-500/10 text-red-500 border-red-500/30",
  PAUSED: "bg-amber-500/10 text-amber-500 border-amber-500/30",
  STOPPING: "bg-sky-500/10 text-sky-500 border-sky-500/30",
  COMPLETED: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
  FAILED: "bg-red-600/15 text-red-500 border-red-600/40",
};

export const StatusBadge = ({ status, testId = "status-badge" }) => {
  const { t } = useApp();
  return (
    <span data-testid={testId}
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider ${STATUS_STYLES[status] || STATUS_STYLES.IDLE}`}>
      {status === "RECORDING" && <span className="h-1.5 w-1.5 rounded-full bg-red-500 rec-pulse" />}
      {t(`status_${status}`)}
    </span>
  );
};

export const DemoBadge = ({ testId = "demo-badge" }) => (
  <span data-testid={testId}
    className="inline-flex items-center rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-500">
    DEMO
  </span>
);

export const Tag = ({ children, tone = "muted", testId }) => {
  const tones = {
    muted: "border-border text-muted-foreground",
    blue: "border-blue-500/30 text-blue-500 bg-blue-500/10",
    green: "border-emerald-500/30 text-emerald-500 bg-emerald-500/10",
    amber: "border-amber-500/30 text-amber-500 bg-amber-500/10",
    red: "border-red-500/30 text-red-500 bg-red-500/10",
  };
  return (
    <span data-testid={testId} className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
};

export const PageHeader = ({ title, sub, children }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-4 fade-up">
    <div>
      <h1 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
      {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
    </div>
    <div className="flex flex-wrap items-center gap-2">{children}</div>
  </div>
);

export const Panel = ({ title, right, children, className = "", testId }) => (
  <section data-testid={testId} className={`rounded-md border border-border bg-card ${className}`}>
    {title && (
      <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{title}</h2>
        {right}
      </header>
    )}
    <div className="p-4">{children}</div>
  </section>
);

export const KV = ({ label, value, mono = true, testId }) => (
  <div className="min-w-0">
    <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
    <div data-testid={testId} className={`mt-0.5 truncate text-sm ${mono ? "font-mono" : ""}`}>
      {value ?? <span className="text-muted-foreground">—</span>}
    </div>
  </div>
);

export const AgentMissing = () => {
  const { t } = useApp();
  return (
    <div data-testid="agent-not-connected-banner" className="rounded-md border border-amber-500/30 bg-amber-500/5 p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
        <div className="min-w-0 space-y-2">
          <p className="font-medium text-amber-500" data-testid="agent-not-connected-message">{t("agent_disconnected")}</p>
          <p className="text-sm text-muted-foreground">{t("agent_not_connected_long")}</p>
          <p className="text-sm text-muted-foreground">{t("agent_howto")}</p>
          <pre className="code-block overflow-x-auto text-xs"><Terminal className="mr-2 inline h-3 w-3" />cd recorder-agent && mvn -q package && java -jar target/recorder-agent.jar agent.properties</pre>
        </div>
      </div>
    </div>
  );
};

export const EmptyState = ({ icon: Icon = CircleDot, text, testId }) => (
  <div data-testid={testId} className="flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-muted-foreground">
    <Icon className="h-6 w-6 opacity-60" />
    <p className="max-w-md">{text}</p>
  </div>
);

export const Confidence = ({ value }) => {
  const pct = Math.round((value ?? 0) * 100);
  const tone = pct >= 85 ? "bg-emerald-500" : pct >= 55 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2" title={`${pct}%`}>
      <div className="h-1.5 w-12 overflow-hidden rounded bg-muted"><div className={`h-full ${tone}`} style={{ width: `${pct}%` }} /></div>
      <span className="font-mono text-[11px] text-muted-foreground">{pct}%</span>
    </div>
  );
};
