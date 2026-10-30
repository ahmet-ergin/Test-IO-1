import { AlertTriangle, Ban, CheckCircle2, Info, KeyRound } from "lucide-react";
import { Tag } from "@/components/common";

const STATUS = {
  OK: ["green", "HAZIR", CheckCircle2], WARNING: ["amber", "UYARI", AlertTriangle], UNSUPPORTED: ["red", "DESTEKLENMİYOR", Ban],
  MANUAL: ["amber", "MANUEL UYARLAMA GEREKLİ", AlertTriangle], REUSED: ["blue", "YENİDEN KULLANILDI", CheckCircle2],
};
const LEVEL = { error: "text-red-500", warning: "text-amber-500", info: "text-muted-foreground" };

const Issue = ({ i }) => (
  <div className={`flex gap-1.5 text-[11px] leading-snug ${LEVEL[i.level]}`}>
    {i.level === "info" ? <Info className="mt-0.5 h-3 w-3 shrink-0" /> : <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />}
    <span><b className="font-mono">{i.code}</b> {i.message}</span>
  </div>
);

const Row = ({ s }) => {
  const [tone, label, Icon] = STATUS[s.status];
  return (
    <div data-testid={`cg-plan-step-${s.order}`} className="grid grid-cols-[36px_110px_1fr_1.2fr_120px] gap-3 border-b border-border px-3 py-3 text-xs last:border-0">
      <span className="font-mono text-muted-foreground">#{s.order}</span>
      <div className="space-y-1"><Tag tone="blue">{s.action}</Tag>{s.sensitive && <span className="flex items-center gap-1 text-[10px] text-amber-500"><KeyRound className="h-3 w-3" />hassas</span>}</div>
      <div className="min-w-0 space-y-1">
        <div className="font-medium" data-testid={`cg-plan-steptext-${s.order}`}>{s.stepText}</div>
        <div className="font-mono text-[10px] text-muted-foreground">{s.methodName}()</div>
        {s.issues.map((i) => <Issue key={i.code} i={i} />)}
      </div>
      <div className="min-w-0 space-y-1">
        {s.selected ? <div data-testid={`cg-plan-locator-${s.order}`} className="break-all font-mono text-[11px] text-primary">{s.selected.strategy === "COORDINATES" ? `W3C tap @ ${s.selected.javaExpr}` : s.selected.javaExpr}</div>
          : s.supported && ["SCROLL", "BACK"].includes(s.action) ? <span className="text-muted-foreground">ekran seviyesi — locator gerekmez</span>
          : <span className="text-red-500">locator yok</span>}
        {s.alternatives.length > 0 && <div className="text-[10px] text-muted-foreground" data-testid={`cg-plan-alts-${s.order}`}>
          {s.alternatives.length} alternatif (yorum satırında): {s.alternatives.map((a) => a.strategy).join(", ")}</div>}
      </div>
      <div><Tag tone={tone} testId={`cg-plan-status-${s.order}`}><Icon className="mr-1 inline h-3 w-3" />{label}</Tag></div>
    </div>
  );
};

export const PlanReview = ({ plan }) => (
  <div data-testid="cg-plan">
    <div className="mb-3 flex flex-wrap gap-2 text-xs" data-testid="cg-plan-summary">
      <Tag>{plan.summary.total} adım</Tag><Tag tone="green">{plan.summary.supported} desteklenen</Tag>
      <Tag tone={plan.summary.unsupported ? "red" : "muted"} testId="cg-plan-unsupported-count">{plan.summary.unsupported} desteklenmeyen</Tag>
      <Tag tone={plan.summary.warnings ? "amber" : "muted"}>{plan.summary.warnings} uyarı</Tag>
    </div>
    {plan.summary.unsupported > 0 && <div data-testid="cg-plan-unsupported-alert" className="mb-3 rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-500">
      Desteklenmeyen adımlar atlanmaz: kodda işaretlenir ve çalıştığında UnsupportedOperationException fırlatır. Bu adımları kendi framework yardımcılarınızla tamamlayın.</div>}
    <div className="rounded border border-border">
      <div className="grid grid-cols-[36px_110px_1fr_1.2fr_120px] gap-3 border-b border-border bg-muted/30 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span>#</span><span>Aksiyon</span><span>Adım metni</span><span>Seçili locator</span><span>Durum</span></div>
      {plan.steps.length ? plan.steps.map((s) => <Row key={s.stepId} s={s} />)
        : <div className="p-6 text-center text-xs text-muted-foreground" data-testid="cg-plan-empty">Bu oturumda adım yok.</div>}
    </div>
  </div>
);
