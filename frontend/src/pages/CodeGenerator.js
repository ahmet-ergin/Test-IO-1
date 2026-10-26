import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Code2, Download, ListChecks, Loader2, RefreshCw, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { http, errMsg } from "@/lib/api";
import { PageHeader, Panel, EmptyState, DemoBadge } from "@/components/common";
import { ConfigPanel } from "@/components/codegen/ConfigPanel";
import { PlanReview } from "@/components/codegen/PlanReview";
import { CodePreview } from "@/components/codegen/CodePreview";
import { ValidationPanel } from "@/components/codegen/ValidationPanel";

const STORAGE = "amts.codegen.config.v1";
const cleanCfg = (c) => ({ ...c, existingStepTexts: (c.existingStepTexts || []).filter((x) => x.trim()) });

const SessionPicker = ({ sessions, value, onChange }) => (
  <Select value={value || ""} onValueChange={onChange}>
    <SelectTrigger data-testid="cg-session-select" className="h-9 w-[340px] text-sm"><SelectValue placeholder="Kayıt oturumu seçin" /></SelectTrigger>
    <SelectContent>
      {sessions.map((s) => (
        <SelectItem key={s.id} value={s.id} data-testid={`cg-session-opt-${s.id}`}>
          <span className="flex items-center gap-2">{s.name}{s.demo && <DemoBadge />}
            <span className="font-mono text-[10px] text-muted-foreground">{s.stepCount} adım · {Object.entries(s.actions).map(([a, n]) => `${a}×${n}`).join(" ")}</span></span>
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

export default function CodeGenerator() {
  const [params, setParams] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(params.get("session"));
  const [cfg, setCfg] = useState(null);
  const [plan, setPlan] = useState(null);
  const [planStale, setPlanStale] = useState(false);
  const [planError, setPlanError] = useState(null);
  const [genValidation, setGenValidation] = useState(null);
  const [files, setFiles] = useState([]);
  const [original, setOriginal] = useState([]);
  const [active, setActive] = useState(0);
  const [validation, setValidation] = useState(null);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState("");
  const [tab, setTab] = useState("review");

  useEffect(() => {
    http.get("/codegen/sessions").then((r) => {
      setSessions(r.data);
      setSessionId((cur) => cur || (r.data.find((s) => s.name === "DENEME-3") || r.data[0])?.id || null);
    }).catch((e) => toast.error(errMsg(e)));
    http.get("/codegen/defaults").then((r) => {
      let saved = {};
      try { saved = JSON.parse(localStorage.getItem(STORAGE) || "{}"); } catch { saved = {}; }
      setCfg({ ...r.data, ...saved, driver: { ...r.data.driver, ...saved.driver }, helper: { ...r.data.helper, ...saved.helper, methods: { ...r.data.helper.methods, ...saved.helper?.methods } } });
    });
  }, []);

  const updateCfg = (c) => { setCfg(c); setPlanStale(true); if (files.length) setStale(true); localStorage.setItem(STORAGE, JSON.stringify(c)); };
  const resetCfg = async () => {
    localStorage.removeItem(STORAGE);
    const { data } = await http.get("/codegen/defaults");
    setCfg(data); setPlan(null); setPlanError(null);
  };

  const review = useCallback(async () => {
    if (!sessionId || !cfg) return;
    setBusy("plan");
    try {
      const { data } = await http.post("/codegen/plan", { sessionId, config: cleanCfg(cfg) });
      setPlan(data); setPlanStale(false); setPlanError(null); setTab("review");
    } catch (e) { setPlanError(errMsg(e)); toast.error(errMsg(e)); } finally { setBusy(""); }
  }, [sessionId, cfg]);

  useEffect(() => { if (sessionId && cfg && !plan && !planError) review(); }, [sessionId, cfg, plan, planError, review]);

  const pick = (id) => { setSessionId(id); setParams({ session: id }); setPlan(null); setPlanError(null); setFiles([]); setValidation(null); };

  const generate = async () => {
    setBusy("gen");
    try {
      const { data } = await http.post("/codegen/generate", { sessionId, config: cleanCfg(cfg) });
      setPlan(data.plan); setPlanStale(false); setPlanError(null); setFiles(data.files); setOriginal(data.files);
      setValidation(data.validation); setGenValidation(data.validation);
      setStale(false); setActive(0); setTab("code");
      toast.success(`Kod üretildi — doğrulama: ${data.validation.status}`);
    } catch (e) { setPlanError(errMsg(e)); toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const validate = async () => {
    setBusy("val");
    try {
      const { data } = await http.post("/codegen/validate", { sessionId, config: cleanCfg(cfg), files });
      setValidation(data); setStale(false);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const downloadZip = async () => {
    setBusy("zip");
    try {
      const r = await http.post("/codegen/zip", { sessionId, config: cleanCfg(cfg), files }, { responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(r.headers["content-disposition"] || "")?.[1] || "amts-gauge.zip";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data); a.download = name; a.click(); URL.revokeObjectURL(a.href);
      const st = r.headers["x-amts-validation"];
      (st === "VERIFIED" ? toast.success : toast.warning)(`ZIP indirildi — doğrulama durumu: ${st} (rapor ZIP içinde: AMTS_VALIDATION.md)`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const edit = (i, content) => {
    setFiles((fs) => {
      const next = fs.map((f, j) => (j === i ? { ...f, content } : f));
      const pristine = !planStale && next.every((f, j) => f.content === original[j]?.content);
      if (pristine) setValidation(genValidation);
      setStale(!pristine);
      return next;
    });
  };
  const reset = (i) => edit(i, original[i].content);

  return (
    <div data-testid="code-generator-page">
      <PageHeader title="Kod Üreteci" sub="Kayıtlı oturumdan mevcut Java + Appium 2 + Gauge framework'ünüze eklenecek .spec ve step dosyaları üretin.">
        <SessionPicker sessions={sessions} value={sessionId} onChange={pick} />
        <Button data-testid="cg-review-btn" variant="outline" size="sm" disabled={!sessionId || !!busy} onClick={review}>
          {busy === "plan" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Adımları incele</Button>
        <Button data-testid="cg-generate-btn" size="sm" disabled={!plan || !!busy} onClick={generate}>
          {busy === "gen" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}Kodu üret</Button>
      </PageHeader>
      {!sessions.length ? <Panel><EmptyState text="Kod üretmek için tamamlanmış bir kayıt oturumu gerekli." testId="cg-no-sessions" /></Panel> : (
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <Panel title="Framework yapılandırması" testId="cg-config" right={<Button data-testid="cg-config-reset" size="sm" variant="ghost" className="h-6 text-[11px]" onClick={resetCfg}>Varsayılanlara dön</Button>}>
            <div className="px-4">{cfg && <ConfigPanel cfg={cfg} onChange={updateCfg} derived={plan?.config} />}</div></Panel>
          <div className="min-w-0 space-y-4">
            {planStale && plan && <div data-testid="cg-plan-stale" className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-500">
              Yapılandırma değişti — güncel adım metinleri için "Adımları incele" veya "Kodu üret"e tıklayın.</div>}
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="review" data-testid="cg-tab-review"><ListChecks className="mr-1.5 h-4 w-4" />1 · Adım incelemesi</TabsTrigger>
                <TabsTrigger value="code" data-testid="cg-tab-code" disabled={!files.length}><Code2 className="mr-1.5 h-4 w-4" />2 · Önizleme & düzenleme</TabsTrigger>
              </TabsList>
              <TabsContent value="review"><Panel testId="cg-review-panel"><div className="p-4">
                {plan ? <PlanReview plan={plan} /> : planError
                  ? <div data-testid="cg-plan-error" className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-500">
                      Yapılandırma hatası: {planError}
                      <Button data-testid="cg-plan-error-reset" size="sm" variant="outline" className="ml-3 h-6 text-[11px]" onClick={resetCfg}>Varsayılanlara dön</Button></div>
                  : <EmptyState text={busy === "plan" ? "İnceleniyor…" : "Bir oturum seçin."} testId="cg-plan-placeholder" />}
              </div></Panel></TabsContent>
              <TabsContent value="code">
                <div className="grid gap-4 2xl:grid-cols-[1fr_340px]">
                  <CodePreview files={files} original={original} active={active} onSelect={setActive} onEdit={edit} onReset={reset} />
                  <div className="space-y-3">
                    <ValidationPanel validation={validation} stale={stale} busy={busy === "val"} onValidate={validate} />
                    <Button data-testid="cg-zip-btn" className="w-full" disabled={!files.length || !!busy} onClick={downloadZip}>
                      {busy === "zip" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}ZIP olarak indir</Button>
                    <p className="text-[10px] text-muted-foreground">ZIP, düzenlediğiniz hâliyle indirilir; sunucu içeriği yeniden doğrular ve sonucu AMTS_VALIDATION.md olarak ekler.</p>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      )}
    </div>
  );
}
