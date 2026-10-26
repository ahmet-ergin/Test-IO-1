import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { http, fmtTime } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { StatusBadge, EmptyState } from "@/components/common";

export const ReplayHistory = ({ sessionId }) => {
  const { t } = useApp();
  const nav = useNavigate();
  const [runs, setRuns] = useState([]);
  useEffect(() => { http.get(`/sessions/${sessionId}/replays`).then((r) => setRuns(r.data)).catch(() => setRuns([])); }, [sessionId]);
  if (!runs.length) return <EmptyState text={t("replay_none")} testId="replay-history-empty" />;
  return (
    <div className="-m-4" data-testid="replay-history">
      {runs.map((r) => (
        <button key={r.id} type="button" data-testid={`replay-history-row-${r.id}`} onClick={() => nav(`/replays/${r.id}`)}
          className="flex w-full items-center gap-4 border-b border-border px-4 py-2.5 text-left transition-colors hover:bg-muted/40">
          <StatusBadge status={r.status} testId={`replay-history-status-${r.id}`} />
          <span className="font-mono text-xs">{r.id.slice(0, 8)}</span>
          <span className="text-xs text-muted-foreground">{fmtTime(r.created_at)}</span>
          <span className="ml-auto truncate font-mono text-xs text-red-500">{r.error?.code}</span>
        </button>
      ))}
    </div>
  );
};
