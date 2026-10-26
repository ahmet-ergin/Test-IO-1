import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Circle, Download, Eraser, Pause, Play, Plus, Save, Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useApp } from "@/context/AppContext";
import { http, errMsg, fmtDuration, downloadExport } from "@/lib/api";
import { useSessionStream } from "@/hooks/useSessionStream";
import { PageHeader, Panel, StatusBadge, KV, AgentMissing, Tag } from "@/components/common";
import { ScreenPreview, useScreen } from "@/components/ScreenPreview";
import { EventFeed } from "@/components/EventFeed";

const KEY = "amts.recorder.session";

const useTicker = (session) => {
  const [now, setNow] = useState(Date.now());
  const [base, setBase] = useState({ ms: 0, at: Date.now() });
  useEffect(() => { setBase({ ms: session?.duration_ms || 0, at: Date.now() }); }, [session]);
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(id); }, []);
  return session?.status === "RECORDING" ? base.ms + (now - base.at) : base.ms;
};

const Controls = ({ status, busy, can, act, t, onClear, onSave, onExport, onNew, saved }) => (
  <div className="flex flex-wrap items-center gap-2" data-testid="recorder-controls">
    {(status === "IDLE") && <Button data-testid="recorder-start-button" disabled={busy || !can} onClick={() => act("start")} className="bg-red-600 text-white hover:bg-red-700"><Circle className="mr-2 h-4 w-4 fill-current" />{t("btn_start")}</Button>}
    {status === "RECORDING" && <Button data-testid="recorder-pause-button" variant="outline" disabled={busy} onClick={() => act("pause")}><Pause className="mr-2 h-4 w-4" />{t("btn_pause")}</Button>}
    {status === "PAUSED" && <Button data-testid="recorder-resume-button" variant="outline" disabled={busy} onClick={() => act("resume")}><Play className="mr-2 h-4 w-4" />{t("btn_resume")}</Button>}
    {["STARTING", "RECORDING", "PAUSED"].includes(status) && <Button data-testid="recorder-stop-button" variant="destructive" disabled={busy} onClick={() => act("stop")}><Square className="mr-2 h-4 w-4" />{t("btn_stop")}</Button>}
    {["COMPLETED", "FAILED"].includes(status) && (<>
      <Button data-testid="recorder-save-button" disabled={busy || saved} onClick={onSave}><Save className="mr-2 h-4 w-4" />{t("btn_save")}</Button>
      <Button data-testid="recorder-export-button" variant="outline" disabled={busy} onClick={onExport}><Download className="mr-2 h-4 w-4" />{t("btn_export")}</Button>
      <Button data-testid="recorder-clear-button" variant="outline" disabled={busy} onClick={onClear}><Eraser className="mr-2 h-4 w-4" />{t("btn_clear")}</Button>
      <Button data-testid="recorder-new-button" variant="ghost" disabled={busy} onClick={onNew}><Plus className="mr-2 h-4 w-4" />{t("btn_new")}</Button>
    </>)}
  </div>
);

export default function Recorder() {
  const { t, status: app, refreshStatus } = useApp();
  const [sessionId, setSessionId] = useState(localStorage.getItem(KEY));
  const [name, setName] = useState("");
  const [pkg, setPkg] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [selected, setSelected] = useState(null);
  const { session, events, mode, setSession } = useSessionStream(sessionId);
  const duration = useTicker(session);
  const latestScreen = useScreen(session?.latest_screen_id, sessionId);

  useEffect(() => { if (app?.activeSession && app.activeSession.id !== sessionId) setSessionId(app.activeSession.id); }, [app, sessionId]);
  useEffect(() => { sessionId ? localStorage.setItem(KEY, sessionId) : localStorage.removeItem(KEY); }, [sessionId]);

  const status = session?.status || "IDLE";
  const device = app?.activeDeviceSerial;
  const canStart = app?.agentConnected && device;

  const act = async (action) => {
    setBusy(true);
    try {
      if (action === "start") {
        const { data } = await http.post("/sessions", { deviceSerial: device, name: name || undefined, packageFilter: pkg || undefined });
        setSessionId(data.id);
      } else {
        setSession((await http.post(`/sessions/${sessionId}/${action}`)).data);
      }
      refreshStatus();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const onSave = async () => {
    try { setSession((await http.patch(`/sessions/${sessionId}`, { saved: true })).data); toast.success(t("rec_saved")); } catch (e) { toast.error(errMsg(e)); }
  };
  const onExport = () => downloadExport(sessionId).catch((e) => toast.error(errMsg(e)));
  const onClear = async () => {
    setConfirmClear(false);
    try { if (!session?.saved) await http.delete(`/sessions/${sessionId}`); setSessionId(null); toast.success(t("rec_cleared")); refreshStatus(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const onClearClick = () => (session?.saved ? onClear() : setConfirmClear(true));
  const highlight = selected || [...events].reverse().find((e) => e.action !== "SCREEN_CHANGE");

  return (
    <div data-testid="recorder-page">
      <PageHeader title={t("recorder_title")} sub={t("recorder_sub")}>
        <Controls status={status} busy={busy} can={canStart} act={act} t={t} saved={session?.saved}
          onClear={onClearClick} onSave={onSave} onExport={onExport} onNew={() => setSessionId(null)} />
      </PageHeader>
      {app && !app.agentConnected && status === "IDLE" && <div className="mb-4"><AgentMissing /></div>}
      {session?.demo && <div className="mb-4 text-sm text-amber-500">DEMO · {t("demo_note")}</div>}
      <Panel testId="recorder-status-bar" className="mb-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <KV label={t("rec_status")} value={<StatusBadge status={status} testId="recorder-status" />} />
          <KV label={t("rec_duration")} value={fmtDuration(duration)} testId="recorder-duration" />
          <KV label={t("rec_actions")} value={session?.event_count ?? 0} testId="recorder-action-count" />
          <KV label={t("active_device")} value={session?.device ? `${session.device.model || ""} · ${session.device.serial}` : device || t("no_active_device")} testId="recorder-device" />
          <KV label={t("rec_package")} value={session?.package_name} testId="recorder-package" />
          <KV label={t("rec_agent")} value={<span className={app?.agentConnected ? "text-emerald-500" : "text-amber-500"}>{app?.agentConnected ? app.agent?.name : t("agent_disconnected")}</span>} testId="recorder-agent-status" />
        </div>
        {status === "IDLE" && (
          <div className="mt-4 grid gap-3 border-t border-border pt-4 md:grid-cols-2">
            <Input data-testid="recorder-session-name-input" placeholder={t("rec_name")} value={name} onChange={(e) => setName(e.target.value)} />
            <Input data-testid="recorder-package-filter-input" placeholder={`${t("rec_pkg_filter")} — com.example.app`} value={pkg} onChange={(e) => setPkg(e.target.value)} className="font-mono" />
            {!canStart && <p className="text-xs text-amber-500 md:col-span-2" data-testid="recorder-start-hint">{t("rec_need_agent")} <Link to="/devices" className="underline">{t("nav_devices")}</Link></p>}
          </div>
        )}
        {session?.error && <div data-testid="recorder-error" className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-500"><span className="font-mono font-semibold">{session.error.code}</span> — {session.error.message}</div>}
      </Panel>
      {session && (
        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <Panel title={t("rec_latest_screen")} testId="recorder-latest-screen"><ScreenPreview screen={latestScreen} highlight={highlight?.screenId === latestScreen?.id ? highlight : null} /></Panel>
          <div className="space-y-4">
            <Panel title={t("rec_live_feed")} right={<Tag tone={mode === "stream" ? "green" : "muted"} testId="recorder-feed-mode">{mode === "stream" ? t("rec_stream") : t("rec_polling")}</Tag>}>
              <EventFeed events={events} onSelect={setSelected} selectedId={selected?.eventId} />
            </Panel>
            {session.limitations?.length > 0 && (
              <Panel title={t("rec_limitations")} testId="recorder-limitations">
                <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{session.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              </Panel>
            )}
            {["COMPLETED", "FAILED"].includes(status) && <Link to={`/recorded-steps/${sessionId}`} className="text-sm text-primary underline" data-testid="recorder-open-steps-link">{t("nav_steps")} →</Link>}
          </div>
        </div>
      )}
      <AlertDialog open={confirmClear} onOpenChange={setConfirmClear}>
        <AlertDialogContent data-testid="recorder-clear-dialog">
          <AlertDialogHeader><AlertDialogTitle>{t("btn_clear")}</AlertDialogTitle><AlertDialogDescription>{t("rec_confirm_clear")}</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="recorder-clear-cancel">{t("btn_cancel")}</AlertDialogCancel>
            <AlertDialogAction data-testid="recorder-clear-confirm" onClick={onClear}>{t("btn_confirm")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
