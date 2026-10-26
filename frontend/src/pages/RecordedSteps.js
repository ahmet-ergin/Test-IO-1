import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowUp, Download, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useApp } from "@/context/AppContext";
import { http, errMsg, artifactUrl, downloadExport } from "@/lib/api";
import { PageHeader, Panel, Tag, Confidence, EmptyState, DemoBadge } from "@/components/common";
import { EventFeed, elementLabel } from "@/components/EventFeed";
import { StepInspector } from "@/components/StepInspector";

const StepRow = ({ step, event, screen, index, total, onInspect, onMove, t }) => {
  const loc = step.locators?.[step.selectedLocatorIndex];
  const thumb = artifactUrl(screen?.screenshotRef);
  return (
    <div data-testid={`step-row-${step.order}`} className="feed-row grid grid-cols-[32px_56px_1fr_auto] items-center gap-3 border-b border-border px-3 py-2.5 hover:bg-muted/40 lg:grid-cols-[32px_56px_1.2fr_1fr_1.4fr_90px_90px_auto]">
      <span className="font-mono text-xs text-muted-foreground">{index + 1}</span>
      <div className="h-14 w-10 overflow-hidden rounded border border-border bg-muted/40">{thumb && <img src={thumb} alt="" className="h-full w-full object-cover object-top" />}</div>
      <div className="min-w-0">
        <div className="flex items-center gap-2"><Tag tone="blue">{step.action}</Tag>{step.verification && <Tag tone="green"><ShieldCheck className="mr-1 h-3 w-3" />{t("verification")}</Tag>}{event?.uncertain && <Tag tone="amber">{t("uncertain")}</Tag>}</div>
        <div className="mt-1 truncate text-sm font-medium" data-testid={`step-name-${step.order}`}>{step.name}</div>
        {step.description && <div className="truncate text-xs text-muted-foreground">{step.description}</div>}
      </div>
      <div className="hidden min-w-0 lg:block"><div className="truncate text-xs">{screen?.screenName || "—"}</div><div className="truncate text-[11px] text-muted-foreground">{elementLabel(event) || t("unavailable")}</div></div>
      <div className="hidden min-w-0 lg:block">{loc ? <><Tag>{loc.strategy}</Tag><div className="mt-1 truncate font-mono text-[11px]" title={loc.value}>{loc.value}</div></> : <span className="text-xs text-muted-foreground">{t("unavailable")}</span>}</div>
      <div className="hidden lg:block"><Confidence value={event?.confidence} /></div>
      <div className="hidden lg:block"><Tag tone={event?.captureSource === "DEMO" ? "amber" : "muted"}>{event?.captureSource}</Tag><div className="mt-1 font-mono text-[10px] text-muted-foreground">{event && new Date(event.timestamp).toLocaleTimeString()}</div></div>
      <div className="flex items-center gap-0.5">
        <Button size="icon" variant="ghost" className="h-7 w-7" disabled={index === 0} onClick={() => onMove(index, -1)} data-testid={`step-move-up-${step.order}`}><ArrowUp className="h-3.5 w-3.5" /></Button>
        <Button size="icon" variant="ghost" className="h-7 w-7" disabled={index === total - 1} onClick={() => onMove(index, 1)} data-testid={`step-move-down-${step.order}`}><ArrowDown className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="outline" className="h-7" onClick={() => onInspect(step)} data-testid={`step-inspect-${step.order}`}>{t("btn_inspect")}</Button>
      </div>
    </div>
  );
};

const ConfirmDialog = ({ open, title, text, onCancel, onConfirm, testId, t }) => (
  <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
    <AlertDialogContent data-testid={testId}>
      <AlertDialogHeader><AlertDialogTitle>{title}</AlertDialogTitle><AlertDialogDescription>{text}</AlertDialogDescription></AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel data-testid={`${testId}-cancel`}>{t("btn_cancel")}</AlertDialogCancel>
        <AlertDialogAction data-testid={`${testId}-confirm`} onClick={onConfirm}>{t("btn_confirm")}</AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

export default function RecordedSteps() {
  const { t } = useApp();
  const { sessionId } = useParams();
  const nav = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [steps, setSteps] = useState([]);
  const [events, setEvents] = useState([]);
  const [screens, setScreens] = useState([]);
  const [inspect, setInspect] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [warned, setWarned] = useState(false);
  const [removeId, setRemoveId] = useState(null);

  useEffect(() => { http.get("/sessions").then((r) => setSessions(r.data)).catch(() => {}); }, []);
  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [s, e, sc] = await Promise.all([http.get(`/sessions/${sessionId}/steps`), http.get(`/sessions/${sessionId}/events`), http.get(`/sessions/${sessionId}/screens`)]);
      setSteps(s.data); setEvents(e.data); setScreens(sc.data);
    } catch (err) { toast.error(errMsg(err)); }
  }, [sessionId]);
  useEffect(() => { load(); }, [load]);

  const evById = useMemo(() => Object.fromEntries(events.map((e) => [e.eventId, e])), [events]);
  const scById = useMemo(() => Object.fromEntries(screens.map((s) => [s.id, s])), [screens]);
  const session = sessions.find((s) => s.id === sessionId);

  const doMove = async ({ index, dir }) => {
    const next = [...steps];
    [next[index], next[index + dir]] = [next[index + dir], next[index]];
    setSteps(next);
    try { await http.post(`/sessions/${sessionId}/steps/reorder`, { order: next.map((s) => s.id) }); load(); } catch (e) { toast.error(errMsg(e)); load(); }
  };
  const onMove = (index, dir) => (warned ? doMove({ index, dir }) : setPendingMove({ index, dir }));
  const remove = async () => {
    const id = removeId; setRemoveId(null);
    try { await http.delete(`/steps/${id}`); setInspect(null); toast.success(t("step_removed")); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const inspectEvent = inspect && evById[inspect.event_id];

  return (
    <div data-testid="recorded-steps-page">
      <PageHeader title={t("steps_title")} sub={t("steps_sub")}>
        <Select value={sessionId || ""} onValueChange={(v) => nav(`/recorded-steps/${v}`)}>
          <SelectTrigger className="w-[280px]" data-testid="steps-session-select"><SelectValue placeholder={t("steps_select_session")} /></SelectTrigger>
          <SelectContent>{sessions.map((s) => <SelectItem key={s.id} value={s.id} data-testid={`steps-session-option-${s.id}`}>{s.demo ? "[DEMO] " : ""}{s.name}</SelectItem>)}</SelectContent>
        </Select>
        {sessionId && <Button variant="outline" size="sm" data-testid="steps-export-button" onClick={() => downloadExport(sessionId).catch((e) => toast.error(errMsg(e)))}><Download className="mr-2 h-4 w-4" />{t("btn_export")}</Button>}
      </PageHeader>
      {session?.demo && <div className="mb-3 flex items-center gap-2 text-sm text-amber-500"><DemoBadge /> {t("demo_note")}</div>}
      {!sessionId ? <Panel><EmptyState text={t("steps_select_session")} testId="steps-no-session" /></Panel> : (
        <Tabs defaultValue="steps">
          <TabsList>
            <TabsTrigger value="steps" data-testid="steps-tab-edited">{t("steps_tab_steps")} · {steps.length}</TabsTrigger>
            <TabsTrigger value="raw" data-testid="steps-tab-raw">{t("steps_tab_raw")} · {events.length}</TabsTrigger>
          </TabsList>
          <TabsContent value="steps">
            <Panel testId="steps-timeline">
              {steps.length === 0 ? <EmptyState text={t("steps_empty")} /> : (
                <div className="-m-4 overflow-hidden">
                  {steps.map((s, i) => <StepRow key={s.id} step={s} event={evById[s.event_id]} screen={scById[evById[s.event_id]?.screenId]} index={i} total={steps.length} onInspect={setInspect} onMove={onMove} t={t} />)}
                </div>
              )}
            </Panel>
          </TabsContent>
          <TabsContent value="raw"><Panel testId="steps-raw-log"><EventFeed events={events} testId="raw-event-log" /></Panel></TabsContent>
        </Tabs>
      )}
      <StepInspector step={inspect} event={inspectEvent} screen={scById[inspectEvent?.screenId]} onClose={() => setInspect(null)}
        onSaved={(s) => { setInspect(s); load(); }} onRemove={() => setRemoveId(inspect.id)} />
      <ConfirmDialog open={!!pendingMove} title={t("reorder_warning_title")} text={t("reorder_warning")} testId="reorder-warning-dialog" t={t}
        onCancel={() => setPendingMove(null)} onConfirm={() => { setWarned(true); doMove(pendingMove); setPendingMove(null); }} />
      <ConfirmDialog open={!!removeId} title={t("btn_remove")} text={t("confirm_remove_step")} testId="remove-step-dialog" t={t}
        onCancel={() => setRemoveId(null)} onConfirm={remove} />
    </div>
  );
}
