import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, CircleDashed, Loader2, MinusCircle, XCircle } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { http, errMsg, fmtTime } from "@/lib/api";
import { PageHeader, Panel, StatusBadge, Tag, KV, EmptyState } from "@/components/common";

const ACTIVE = ["QUEUED", "RUNNING"];
const STEP_ICON = {
  PASSED: <CheckCircle2 className="h-4 w-4 text-emerald-500" />, FAILED: <XCircle className="h-4 w-4 text-red-500" />,
  SKIPPED: <MinusCircle className="h-4 w-4 text-muted-foreground" />, PENDING: <CircleDashed className="h-4 w-4 text-muted-foreground" />,
};

const StepResult = ({ s, running, t }) => (
  <div data-testid={`replay-step-${s.order}`} className="grid grid-cols-[24px_32px_1fr] gap-3 border-b border-border px-3 py-3 last:border-0">
    <span className="pt-0.5">{running && s.status === "PENDING" ? <Loader2 className="h-4 w-4 animate-spin text-sky-500" /> : STEP_ICON[s.status]}</span>
    <span className="pt-0.5 font-mono text-xs text-muted-foreground">#{s.order}</span>
    <div className="min-w-0 space-y-1">
      <div className="flex flex-wrap items-center gap-2"><Tag tone="blue">{s.action}</Tag><span className="text-sm font-medium">{s.name}</span>
        <Tag tone={s.status === "PASSED" ? "green" : s.status === "FAILED" ? "red" : "muted"} testId={`replay-step-status-${s.order}`}>{t(`status_${s.status}`)}</Tag>
        {s.durationMs != null && <span className="font-mono text-[11px] text-muted-foreground">{s.durationMs} ms</span>}</div>
      {s.locator && <div className="truncate font-mono text-[11px] text-muted-foreground" data-testid={`replay-step-locator-${s.order}`}>{s.locator.strategy} · {s.locator.value}</div>}
      {s.error && <div data-testid={`replay-step-error-${s.order}`} className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 font-mono text-xs text-red-500">{s.error.code}: {s.error.message}</div>}
      {s.attempts?.length > 0 && <div className="flex flex-wrap gap-1">{s.attempts.map((a) => <Tag key={a.strategy}>{a.strategy}: {a.matchCount ?? "err"}</Tag>)}</div>}
    </div>
  </div>
);

export default function ReplayRun() {
  const { t } = useApp();
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => http.get(`/replays/${runId}`).then((r) => { setRun(r.data); setError(null); }).catch((e) => setError(errMsg(e))), [runId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!run || !ACTIVE.includes(run.status)) return undefined;
    const id = setInterval(load, 1000);
    return () => clearInterval(id);
  }, [run, load]);

  if (error) return <Panel><EmptyState text={error} testId="replay-run-error" /></Panel>;
  if (!run) return <Panel><EmptyState text={t("replay_loading")} testId="replay-run-loading" /></Panel>;
  const done = run.steps.filter((s) => s.status !== "PENDING").length;
  const pct = Math.round((done / Math.max(run.steps.length, 1)) * 100);
  const running = ACTIVE.includes(run.status);
  return (
    <div data-testid="replay-run-page">
      <PageHeader title={t("replay_title")} sub={run.session_name}>
        <Link to={`/recorded-steps/${run.session_id}`} data-testid="replay-back-link" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />{t("nav_steps")}</Link>
      </PageHeader>
      <Panel testId="replay-summary" className="mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <StatusBadge status={run.status} testId="replay-status" />
          <div className="h-2 min-w-[200px] flex-1 overflow-hidden rounded bg-muted" data-testid="replay-progress">
            <div className={`h-full transition-[width] duration-500 ${run.status === "FAILED" ? "bg-red-500" : run.status === "PASSED" ? "bg-emerald-500" : "bg-sky-500"}`} style={{ width: `${running && run.status === "QUEUED" ? 4 : pct}%` }} />
          </div>
          <span className="font-mono text-xs text-muted-foreground" data-testid="replay-progress-text">{done}/{run.steps.length}</span>
        </div>
        {run.status === "QUEUED" && <p className="mt-3 text-sm text-muted-foreground" data-testid="replay-queued-note">{t("replay_queued_note")}</p>}
        {run.error && <div data-testid="replay-error" className="mt-3 rounded border border-red-500/30 bg-red-500/5 px-3 py-2 font-mono text-xs text-red-500">{run.error.code}: {run.error.message}</div>}
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-5">
          <KV label={t("replay_device")} value={`${run.device?.model || ""} · ${run.device?.serial}`} testId="replay-device" />
          <KV label={t("replay_app")} value={run.app_package} testId="replay-package" />
          <KV label={t("replay_activity")} value={run.app_activity?.replace(run.app_package, "")} testId="replay-activity" />
          <KV label={t("replay_started")} value={fmtTime(run.started_at)} mono={false} />
          <KV label="Run ID" value={run.id.slice(0, 8)} testId="replay-run-id" />
        </div>
      </Panel>
      <Panel title={t("replay_steps")} testId="replay-steps"><div className="-m-4">{run.steps.map((s) => <StepResult key={s.stepId} s={s} t={t} running={run.status === "RUNNING"} />)}</div></Panel>
    </div>
  );
}
