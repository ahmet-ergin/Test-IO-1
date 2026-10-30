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
import { PomConfigPanel } from "@/components/codegen/PomConfigPanel";
import { PlanReview } from "@/components/codegen/PlanReview";
import { CodePreview } from "@/components/codegen/CodePreview";
import { ValidationPanel } from "@/components/codegen/ValidationPanel";
import { ProfileManager } from "@/components/codegen/ProfileManager";
import { useProfiles, describe, initialProfile, PROFILE_KEY } from "@/lib/codegenProfiles";

const POM_NOTE = "Paket/import/sınıf ilişkileri ve Java sözdizimi javac ile, kurum içi framework sınıfları yerine yerel stub'lar kullanılarak derlenir. "
  + "Framework metot imzaları (şablonlarınız) doğrulanamaz; gerçek derleme için projenizde mvn test-compile çalıştırın.";
const cleanCfg = (c) => ({ ...c, existingStepTexts: (c.existingStepTexts || []).filter((x) => x.trim()),
  ...(c.existingClassNames ? { existingClassNames: c.existingClassNames.filter((x) => x.trim()) } : {}),
  ...(c.existingPageMethods ? { existingPageMethods: c.existingPageMethods.filter((x) => x.trim()) } : {}) });
const tid = (k) => k.replace(/:/g, "-");

const ProfilePicker = ({ value, options, onChange }) => (
  <Select value={options.some(([k]) => k === value) ? value : undefined} onValueChange={onChange}>
    <SelectTrigger data-testid="cg-profile-select" className="h-9 w-[300px] text-sm"><SelectValue placeholder="Profil yükleniyor…" /></SelectTrigger>
    <SelectContent>{options.map(([k, label]) => <SelectItem key={k} value={k} data-testid={`cg-profile-opt-${tid(k)}`}>{label}</SelectItem>)}</SelectContent>
  </Select>
);

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
  const [genCfg, setGenCfg] = useState("");
  const [files, setFiles] = useState([]);
  const [original, setOriginal] = useState([]);
  const [active, setActive] = useState(0);
  const [validation, setValidation] = useState(null);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState("");
  const [tab, setTab] = useState("review");
  const [profile, setProfile] = useState(initialProfile);
  const store = useProfiles();
  const P = describe(profile);

  useEffect(() => {
    http.get("/codegen/sessions").then((r) => {
      setSessions(r.data);
      setSessionId((cur) => cur || (r.data.find((s) => s.name === "DENEME-3") || r.data[0])?.id || null);
    }).catch((e) => toast.error(errMsg(e)));
  }, []);

  useEffect(() => {
    setCfg(null); setPlan(null); setPlanError(null); setFiles([]); setOriginal([]); setValidation(null); setStale(false); setTab("review");
    let live = true;
    if (P.kind === "GAUGE") {
      http.get("/codegen/defaults").then((r) => { if (live) setCfg(store.loadCfg(profile, r.data)); }).catch((e) => toast.error(errMsg(e)));
    } else if (store.builtins) {
      const d = store.defaultsFor(profile);
      if (d) setCfg(store.loadCfg(profile, d));
      else if (store.builtins.length) changeProfile("POM:GENERIC");
      else changeProfile("GAUGE");
    }
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, store.builtins]);

  function changeProfile(p) {
    if (p === profile) return;
    localStorage.setItem(PROFILE_KEY, p); setCfg(null); setPlan(null); setPlanStale(false); setFiles([]); setOriginal([]); setValidation(null); setProfile(p);
  }
  const updateCfg = (c) => { setCfg(c); setPlanStale(true); if (files.length) setStale(true); store.saveCfg(profile, c); };
  const resetCfg = async () => {
    try {
      const data = P.kind === "GAUGE" ? (await http.get("/codegen/defaults")).data : store.defaultsFor(profile);
      store.clearCfg(profile, data);
      setCfg(data); setPlanError(null); setPlanStale(true);
      if (files.length) setStale(true); else setPlan(null);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const review = useCallback(async () => {
    if (!sessionId || !cfg) return;
    setBusy("plan");
    try {
      const { data } = await http.post(`${P.base}/plan`, { sessionId, config: cleanCfg(cfg) });
      setPlan(data); setPlanStale(false); setPlanError(null); setTab("review");
    } catch (e) { setPlanError(errMsg(e)); toast.error(errMsg(e)); } finally { setBusy(""); }
  }, [sessionId, cfg, P.base]);

  useEffect(() => { if (sessionId && cfg && !plan && !planError) review(); }, [sessionId, cfg, plan, planError, review]);

  const pick = (id) => { setSessionId(id); setParams({ session: id }); setPlan(null); setPlanError(null); setFiles([]); setValidation(null); };

  const generate = async () => {
    setBusy("gen");
    try {
      const { data } = await http.post(`${P.base}/generate`, { sessionId, config: cleanCfg(cfg) });
      setPlan(data.plan); setPlanStale(false); setPlanError(null); setFiles(data.files); setOriginal(data.files);
      setValidation(data.validation); setGenValidation(data.validation); setGenCfg(JSON.stringify(cleanCfg(cfg)));
      setStale(false); setActive(0); setTab("code");
      toast.success(`Kod üretildi — doğrulama: ${data.validation.status}`);
    } catch (e) { setPlanError(errMsg(e)); toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const validate = async () => {
    setBusy("val");
    try {
      const { data } = await http.post(`${P.base}/validate`, { sessionId, config: cleanCfg(cfg), files });
      setValidation(data); setStale(false);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const downloadZip = async () => {
    setBusy("zip");
    try {
      const r = await http.post(`${P.base}/zip`, { sessionId, config: cleanCfg(cfg), files }, { responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(r.headers["content-disposition"] || "")?.[1] || "amts-code.zip";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data); a.download = name; a.click(); URL.revokeObjectURL(a.href);
      const st = r.headers["x-amts-validation"];
      (st === "VERIFIED" || st === "STRUCTURE_VERIFIED" ? toast.success : toast.warning)(`ZIP indirildi — doğrulama durumu: ${st} (rapor ZIP içinde: AMTS_VALIDATION.md)`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  const edit = (i, content) => {
    setFiles((fs) => {
      const next = fs.map((f, j) => (j === i ? { ...f, content } : f));
      const pristine = JSON.stringify(cleanCfg(cfg)) === genCfg && next.every((f, j) => f.content === original[j]?.content);
      if (pristine) setValidation(genValidation);
      setStale(!pristine);
      return next;
    });
  };
  const reset = (i) => edit(i, original[i].content);

  return (
    <div data-testid="code-generator-page">
      <PageHeader title="Kod Üreteci" sub={profile === "GAUGE" ? "Kayıtlı oturumdan mevcut Java + Appium 2 + Gauge framework'ünüze eklenecek .spec ve step dosyaları üretin."
        : "Kayıtlı oturumdan mevcut Cucumber + Page Object projenize eklenecek Step Definition, Page Interface, Android Page ve Türkçe .feature üretin."}>
        <ProfilePicker value={profile} options={store.options} onChange={changeProfile} />
        <SessionPicker sessions={sessions} value={sessionId} onChange={pick} />
        <Button data-testid="cg-review-btn" variant="outline" size="sm" disabled={!sessionId || !!busy} onClick={review}>
          {busy === "plan" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Adımları incele</Button>
        <Button data-testid="cg-generate-btn" size="sm" disabled={!plan || !!busy} onClick={generate}>
          {busy === "gen" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}Kodu üret</Button>
      </PageHeader>
      {!sessions.length ? <Panel><EmptyState text="Kod üretmek için tamamlanmış bir kayıt oturumu gerekli." testId="cg-no-sessions" /></Panel> : (
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <Panel title="Framework yapılandırması" testId="cg-config" right={<Button data-testid="cg-config-reset" size="sm" variant="ghost" className="h-6 text-[11px]" onClick={resetCfg}>Varsayılanlara dön</Button>}>
            <div className="px-4">{cfg && (profile === "GAUGE" ? <ConfigPanel cfg={cfg} onChange={updateCfg} derived={plan?.config} />
              : <><ProfileManager profileKey={profile} cfg={cfg} store={store} onSelect={changeProfile} />
                <PomConfigPanel cfg={cfg} onChange={updateCfg} derived={plan?.config} /></>)}</div></Panel>
          <div className="min-w-0 space-y-4">
            {planStale && plan && <div data-testid="cg-plan-stale" className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-500">
              Yapılandırma değişti — güncel adım metinleri için "Adımları incele" veya "Kodu üret"e tıklayın.</div>}
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="review" data-testid="cg-tab-review"><ListChecks className="mr-1.5 h-4 w-4" />1 · Adım incelemesi</TabsTrigger>
                <TabsTrigger value="code" data-testid="cg-tab-code" disabled={!files.length}><Code2 className="mr-1.5 h-4 w-4" />2 · Önizleme & düzenleme</TabsTrigger>
              </TabsList>
              <TabsContent value="review"><Panel testId="cg-review-panel"><div className="p-4">
                {plan?.classConflicts?.length > 0 && <div data-testid="cg-class-conflicts" className="mb-3 rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-500">
                  Projenizde mevcut sınıflar: {plan.classConflicts.join(", ")}. Bu sınıflar için tam dosya yerine yalnızca eklenecek parça (.amts-members.txt) üretilir; otomatik birleştirme yapılmaz.</div>}
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
                    <ValidationPanel validation={validation} stale={stale} busy={busy === "val"} onValidate={validate} {...(profile === "GAUGE" ? {} : { footnote: POM_NOTE })} />
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
