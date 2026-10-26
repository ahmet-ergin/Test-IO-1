import { useCallback, useEffect, useState } from "react";
import { Copy, KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApp } from "@/context/AppContext";
import { http, errMsg, fmtTime } from "@/lib/api";
import { PageHeader, Panel, Tag } from "@/components/common";

const Row = ({ label, children }) => (
  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border py-3 last:border-0">
    <span className="text-sm">{label}</span><div className="flex items-center gap-2">{children}</div>
  </div>
);

const AgentPairing = ({ configured, onRotated }) => {
  const { t } = useApp();
  const [token, setToken] = useState(null);
  const rotate = async () => {
    try { setToken((await http.post("/settings/agent-token")).data.token); onRotated(); } catch (e) { toast.error(errMsg(e)); }
  };
  const props = `backend.url=${process.env.REACT_APP_BACKEND_URL}\nagent.token=${token || "<generate a token>"}\nadb.path=adb`;
  return (
    <Panel title={t("s_agent")} testId="settings-agent-panel">
      <p className="mb-3 text-sm text-muted-foreground">{t("s_agent_desc")}</p>
      <div className="mb-3 flex items-center gap-3">
        <Tag tone={configured ? "green" : "amber"} testId="settings-token-status">{configured ? t("s_token_configured") : t("s_token_missing")}</Tag>
        <Button size="sm" variant="outline" onClick={rotate} data-testid="settings-generate-token-button"><KeyRound className="mr-2 h-4 w-4" />{t("btn_generate_token")}</Button>
      </div>
      {token && <p className="mb-2 text-xs text-amber-500" data-testid="settings-token-warning">{t("s_token_once")}</p>}
      <div className="relative">
        <pre className="code-block overflow-x-auto text-xs" data-testid="settings-agent-properties">{props}</pre>
        {token && <Button size="icon" variant="ghost" className="absolute right-1 top-1 h-7 w-7 text-gray-300" data-testid="settings-copy-properties-button"
          onClick={() => navigator.clipboard.writeText(props).then(() => toast.success("OK"))}><Copy className="h-3.5 w-3.5" /></Button>}
      </div>
    </Panel>
  );
};

export default function Settings() {
  const { t, lang, setLang, theme, setTheme, refreshStatus } = useApp();
  const [s, setS] = useState(null);
  const [keywords, setKeywords] = useState("");
  const [audit, setAudit] = useState([]);
  const load = useCallback(async () => {
    const [{ data }, { data: logs }] = await Promise.all([http.get("/settings"), http.get("/audit-logs?limit=50")]);
    setS(data); setKeywords(data.mask_keywords.join(", ")); setAudit(logs);
  }, []);
  useEffect(() => { load().catch((e) => toast.error(errMsg(e))); }, [load]);

  const save = async () => {
    try {
      const body = { capture_interval_ms: Number(s.capture_interval_ms), capture_screenshots: s.capture_screenshots,
        redact_sensitive_regions: s.redact_sensitive_regions, retention_days: Number(s.retention_days),
        external_ai_consent: s.external_ai_consent, mask_keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean) };
      await http.put("/settings", body); toast.success(t("s_saved")); load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const purge = async () => {
    try { const { data } = await http.post("/retention/purge"); toast.success(`${t("s_purged")}: ${data.deleted}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  if (!s) return null;
  const set = (k) => (v) => setS({ ...s, [k]: v });

  return (
    <div data-testid="settings-page">
      <PageHeader title={t("settings_title")} sub={t("settings_sub")}>
        <Button data-testid="settings-save-button" onClick={save}>{t("btn_save_settings")}</Button>
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-2">
        <AgentPairing configured={s.agent_token_configured} onRotated={() => { load(); refreshStatus(); }} />
        <Panel title={t("s_capture")} testId="settings-capture-panel">
          <Row label={t("s_interval")}><Input type="number" min={500} className="w-32 font-mono" data-testid="settings-interval-input" value={s.capture_interval_ms} onChange={(e) => set("capture_interval_ms")(e.target.value)} /></Row>
          <Row label={t("s_screenshots")}><Switch data-testid="settings-screenshots-switch" checked={s.capture_screenshots} onCheckedChange={set("capture_screenshots")} /></Row>
          <Row label={t("s_redact")}><Switch data-testid="settings-redact-switch" checked={s.redact_sensitive_regions} onCheckedChange={set("redact_sensitive_regions")} /></Row>
        </Panel>
        <Panel title={t("s_security")} testId="settings-security-panel">
          <label className="text-sm">{t("s_keywords")}</label>
          <Input className="mt-2 font-mono text-xs" data-testid="settings-keywords-input" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          <Row label={t("s_consent")}><Switch data-testid="settings-consent-switch" checked={s.external_ai_consent} onCheckedChange={set("external_ai_consent")} /></Row>
        </Panel>
        <Panel title={t("s_retention")} testId="settings-retention-panel">
          <Row label={t("s_retention_days")}><Input type="number" min={1} className="w-24 font-mono" data-testid="settings-retention-input" value={s.retention_days} onChange={(e) => set("retention_days")(e.target.value)} /></Row>
          <Row label={t("s_purge_desc")}><Button variant="outline" size="sm" data-testid="settings-purge-button" onClick={purge}><Trash2 className="mr-2 h-4 w-4" />{t("btn_purge")}</Button></Row>
        </Panel>
        <Panel title={t("s_ui")} testId="settings-ui-panel">
          <Row label={t("s_language")}>
            {["tr", "en"].map((l) => <Button key={l} size="sm" variant={lang === l ? "default" : "outline"} data-testid={`settings-lang-${l}`} onClick={() => setLang(l)}>{l.toUpperCase()}</Button>)}
          </Row>
          <Row label={t("s_theme")}>
            {["dark", "light"].map((m) => <Button key={m} size="sm" variant={theme === m ? "default" : "outline"} data-testid={`settings-theme-${m}`} onClick={() => setTheme(m)}>{t(`theme_${m}`)}</Button>)}
          </Row>
        </Panel>
        <Panel title={t("s_audit")} testId="settings-audit-panel">
          <div className="max-h-72 overflow-y-auto">
            <Table><TableHeader><TableRow><TableHead>{t("col_time")}</TableHead><TableHead>Action</TableHead><TableHead>Target</TableHead></TableRow></TableHeader>
              <TableBody>{audit.map((a) => (
                <TableRow key={a.id}><TableCell className="text-xs">{fmtTime(a.timestamp)}</TableCell><TableCell className="font-mono text-xs">{a.action}</TableCell><TableCell className="truncate font-mono text-[11px] text-muted-foreground">{a.target?.slice(0, 12) || "—"}</TableCell></TableRow>
              ))}</TableBody></Table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
