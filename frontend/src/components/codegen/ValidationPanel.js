import { CheckCircle2, CircleDashed, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

const CHECK_NAMES = {
  gauge_match: "Gauge adım ↔ @Step eşleşmesi", step_collisions: "Mevcut step metni çakışması", javac: "Java derleme (javac)",
  structure: "Katmanlar: paket, import, extends/implements, @PageModel, @FindBy", feature_match: "Feature adımı ↔ Cucumber tanımı eşleşmesi",
  java_syntax: "Java sözdizimi ve dosyalar arası derleme (stub'larla)", framework_compile: "Kurum içi framework'e karşı derleme",
  class_collisions: "Mevcut sınıf adı çakışması",
};
const ICON = {
  PASS: <CheckCircle2 className="h-4 w-4 text-emerald-500" />, FAIL: <XCircle className="h-4 w-4 text-red-500" />,
  SKIPPED: <CircleDashed className="h-4 w-4 text-muted-foreground" />, PARTIAL: <CircleDashed className="h-4 w-4 text-amber-500" />,
  WARN: <CircleDashed className="h-4 w-4 text-amber-500" />,
  NOT_VERIFIED: <CircleDashed className="h-4 w-4 text-amber-500" />,
};
const BANNER = {
  VERIFIED: ["border-emerald-500/30 bg-emerald-500/10 text-emerald-500", "DOĞRULANDI — sözdizimi derlendi ve Gauge adımları birebir eşleşiyor"],
  STRUCTURE_VERIFIED: ["border-sky-500/30 bg-sky-500/10 text-sky-500", "YAPISAL OLARAK DOĞRULANDI — kurum içi framework'e karşı derleme DOĞRULANMADI"],
  FAILED: ["border-red-500/30 bg-red-500/10 text-red-500", "BAŞARISIZ — aşağıdaki hataları düzeltin"],
  NOT_VERIFIED: ["border-amber-500/30 bg-amber-500/10 text-amber-500", "DOĞRULANMADI — seçilen Java sürümü için derleme doğrulaması yapılamadı"],
  STALE: ["border-amber-500/30 bg-amber-500/10 text-amber-500", "DEĞİŞTİRİLDİ — kod düzenlendi, doğrulanmadı"],
};
const GAUGE_NOTE = "Derleme; seçilen Java sürümü, Appium java-client 9.5.0 / Selenium 4.34 / gauge-java 0.11.1 ile yapılır. Mevcut framework sınıflarınız "
  + "(driver, temel sınıf, yardımcılar) yalnızca derleme amaçlı stub ile temsil edilir; gerçek imzalarınız farklıysa projenizde ayrıca derleyin.";

export const ValidationPanel = ({ validation, stale, busy, onValidate, footnote = GAUGE_NOTE }) => {
  const key = stale || !validation ? "STALE" : validation.status;
  const [cls, text] = BANNER[key];
  return (
    <div className="space-y-3" data-testid="cg-validation-panel">
      <div className={`flex items-center justify-between gap-3 rounded border px-3 py-2 text-xs font-semibold ${cls}`} data-testid="cg-validation-status" data-status={key}>
        <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 shrink-0" />{text}</span>
        <Button data-testid="cg-validate-btn" size="sm" variant="outline" className="h-7 text-xs" disabled={busy} onClick={onValidate}>
          {busy ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}Doğrula</Button>
      </div>
      {validation && !stale && validation.checks.map((c) => (
        <div key={c.id} data-testid={`cg-check-${c.id}`} className="rounded border border-border px-3 py-2">
          <div className="flex items-center gap-2 text-xs font-medium">{ICON[c.status]}{CHECK_NAMES[c.id] || c.id}
            <span className="ml-auto font-mono text-[10px] text-muted-foreground" data-testid={`cg-check-${c.id}-status`}>{c.status}</span></div>
          <p className="mt-1 text-[11px] text-muted-foreground">{c.summary}</p>
          {c.details.length > 0 && <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted/40 p-2 font-mono text-[10px] text-red-500">{c.details.join("\n")}</pre>}
        </div>
      ))}
      <p className="text-[10px] leading-snug text-muted-foreground">{footnote}</p>
    </div>
  );
};
