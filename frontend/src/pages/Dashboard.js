import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Database, Smartphone, Video } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { http, fmtDuration, fmtTime } from "@/lib/api";
import { PageHeader, Panel, StatusBadge, DemoBadge, Tag, AgentMissing, EmptyState } from "@/components/common";

const Metric = ({ icon: Icon, label, value, testId }) => (
  <div className="rounded-md border border-border bg-card p-4">
    <div className="flex items-center justify-between text-muted-foreground">
      <span className="text-[11px] uppercase tracking-wider">{label}</span><Icon className="h-4 w-4" />
    </div>
    <div data-testid={testId} className="mt-2 font-mono text-2xl font-semibold">{value}</div>
  </div>
);

const MODULES = [
  ["Mobile Interaction Recorder (Android)", true], ["Locator Engine — basic extraction", true],
  ["Locator Engine — scoring & on-device validation", false], ["AI Screen & Action Understanding", false],
  ["Framework-Aware Code Generator (Java/Gauge)", true], ["Jira / Zephyr Scale Integration", false],
  ["iOS Recorder", false],
];

export default function Dashboard() {
  const { t, status } = useApp();
  const [sessions, setSessions] = useState([]);
  useEffect(() => { http.get("/sessions?limit=8").then((r) => setSessions(r.data)).catch(() => {}); }, []);
  const active = status?.activeSession;
  return (
    <div data-testid="dashboard-page">
      <PageHeader title={t("dash_title")} sub={t("dash_sub")} />
      {status && !status.agentConnected && <div className="mb-6"><AgentMissing /></div>}
      <div className="stagger mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric icon={Smartphone} label={t("dash_devices_online")} value={status?.onlineDevices ?? "—"} testId="metric-devices-online" />
        <Metric icon={Video} label={t("dash_active")} value={active ? t(`status_${active.status}`) : t("none")} testId="metric-active-recording" />
        <Metric icon={Database} label={t("dash_sessions")} value={status?.stats.sessions ?? "—"} testId="metric-sessions" />
        <Metric icon={Activity} label={t("dash_events")} value={status?.stats.events ?? "—"} testId="metric-events" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title={t("dash_recent")} className="lg:col-span-2" testId="dashboard-recent-sessions">
          {sessions.length === 0 ? <EmptyState text={t("sessions_empty")} /> : (
            <ul className="divide-y divide-border">
              {sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 py-2.5">
                  <Link to={`/recorded-steps/${s.id}`} className="min-w-0 hover:text-primary" data-testid={`dashboard-session-${s.id}`}>
                    <div className="flex items-center gap-2 truncate text-sm font-medium">{s.demo && <DemoBadge />}{s.name}</div>
                    <div className="truncate font-mono text-[11px] text-muted-foreground">
                      {s.device?.model} · {s.package_name || "—"} · {fmtTime(s.created_at)}
                    </div>
                  </Link>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="font-mono text-xs text-muted-foreground">{s.event_count} ev · {fmtDuration(s.duration_ms)}</span>
                    <StatusBadge status={s.status} testId={`dashboard-session-status-${s.id}`} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title={t("dash_modules")} testId="dashboard-module-status">
          <ul className="space-y-2">
            {MODULES.map(([name, done]) => (
              <li key={name} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{name}</span>
                <Tag tone={done ? "green" : "muted"}>{done ? t("implemented") : t("planned_short")}</Tag>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
