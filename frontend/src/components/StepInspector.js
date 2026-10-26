import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { http, errMsg } from "@/lib/api";
import { Tag, KV } from "@/components/common";
import { ScreenPreview } from "@/components/ScreenPreview";

const LocatorOption = ({ c, i, selected, onPick, t }) => {
  const u = c.uniqueness || {};
  const uText = !u.checked ? t("unique_unchecked") : u.unique ? t("unique_yes") : `${t("unique_no")} (${u.matchCount})`;
  return (
    <button onClick={() => onPick(i)} data-testid={`locator-option-${i}`}
      className={`w-full rounded border p-2 text-left transition-colors ${selected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"}`}>
      <div className="flex items-center justify-between gap-2">
        <Tag tone={selected ? "blue" : "muted"}>{c.strategy}</Tag>
        <span className="font-mono text-[10px] text-muted-foreground">{Math.round(c.confidence * 100)}% · {uText}</span>
      </div>
      <div className="mt-1 break-all font-mono text-xs">{c.value}</div>
    </button>
  );
};

const Details = ({ step, event, onSaved, onRemove }) => {
  const { t } = useApp();
  const [form, setForm] = useState({ name: step.name, description: step.description || "", verification: step.verification, selectedLocatorIndex: step.selectedLocatorIndex });
  useEffect(() => setForm({ name: step.name, description: step.description || "", verification: step.verification, selectedLocatorIndex: step.selectedLocatorIndex }), [step]);
  const save = async () => {
    try {
      const body = { ...form };
      if (body.selectedLocatorIndex == null) delete body.selectedLocatorIndex;
      onSaved((await http.patch(`/steps/${step.id}`, body)).data); toast.success(t("step_saved"));
    } catch (e) { toast.error(errMsg(e)); }
  };
  const el = event?.element;
  return (
    <div className="space-y-4">
      <div><label className="text-xs text-muted-foreground">{t("step_name")}</label>
        <Input data-testid="step-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div><label className="text-xs text-muted-foreground">{t("step_description")}</label>
        <Textarea data-testid="step-description-input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
      <div className="flex items-center justify-between rounded border border-border p-3">
        <span className="text-sm">{t("step_verification")}</span>
        <Switch data-testid="step-verification-switch" checked={form.verification} onCheckedChange={(v) => setForm({ ...form, verification: v })} />
      </div>
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">{t("step_locator")}</div>
        {step.locators?.length ? step.locators.map((c, i) => (
          <LocatorOption key={i} c={c} i={i} t={t} selected={form.selectedLocatorIndex === i} onPick={(idx) => setForm({ ...form, selectedLocatorIndex: idx })} />
        )) : <p className="text-xs text-muted-foreground">{t("unavailable")}</p>}
      </div>
      {event && (
        <div className="grid grid-cols-2 gap-3 rounded border border-border p-3">
          <KV label="resourceId" value={el?.resourceId} /><KV label="className" value={el?.className} />
          <KV label="text" value={el?.text} /><KV label="contentDesc" value={el?.contentDesc} />
          <KV label="bounds" value={el?.bounds ? `[${el.bounds.join(", ")}]` : null} />
          <KV label="coordinates" value={event.coordinates ? `${event.coordinates.x}, ${event.coordinates.y}` : null} />
          <KV label="captureSource" value={event.captureSource} /><KV label="confidence" value={event.confidence} />
        </div>
      )}
      {event?.limitations?.length > 0 && <ul className="list-disc pl-5 text-xs text-amber-500">{event.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
      <div className="flex justify-between gap-2">
        <Button variant="destructive" size="sm" data-testid="step-remove-button" onClick={onRemove}>{t("btn_remove")}</Button>
        <Button size="sm" data-testid="step-save-button" onClick={save}>{t("btn_save_step")}</Button>
      </div>
    </div>
  );
};

const XmlView = ({ refId }) => {
  const [xml, setXml] = useState(null);
  useEffect(() => {
    if (!refId) return;
    http.get(`/artifacts/${refId}`, { responseType: "text", transformResponse: (d) => d }).then((r) => setXml(r.data)).catch(() => setXml(""));
  }, [refId]);
  if (!refId) return <p className="text-xs text-muted-foreground">—</p>;
  return <pre data-testid="step-xml-view" className="code-block max-h-[60vh] overflow-auto whitespace-pre-wrap break-all text-[11px]">{xml ?? "…"}</pre>;
};

export const StepInspector = ({ step, event, screen, onClose, onSaved, onRemove }) => {
  const { t } = useApp();
  return (
    <Sheet open={!!step} onOpenChange={(o) => !o && onClose()}>
      <SheetContent data-testid="inspect-step-drawer" className="w-full overflow-y-auto sm:max-w-xl">
        {step && (<>
          <SheetHeader><SheetTitle className="font-heading">#{step.order} · {step.action}</SheetTitle></SheetHeader>
          <Tabs defaultValue="details" className="mt-4">
            <TabsList>
              <TabsTrigger value="details" data-testid="inspect-tab-details">{t("tab_details")}</TabsTrigger>
              <TabsTrigger value="event" data-testid="inspect-tab-event">{t("tab_event")}</TabsTrigger>
              <TabsTrigger value="xml" data-testid="inspect-tab-xml">{t("tab_xml")}</TabsTrigger>
              <TabsTrigger value="shot" data-testid="inspect-tab-screenshot">{t("tab_screenshot")}</TabsTrigger>
            </TabsList>
            <TabsContent value="details"><Details step={step} event={event} onSaved={onSaved} onRemove={onRemove} /></TabsContent>
            <TabsContent value="event"><pre data-testid="step-event-json" className="code-block max-h-[65vh] overflow-auto text-[11px]">{JSON.stringify(event, null, 2)}</pre></TabsContent>
            <TabsContent value="xml"><XmlView refId={event?.hierarchyRef} /></TabsContent>
            <TabsContent value="shot"><ScreenPreview screen={screen} highlight={event} testId="step-screenshot" /></TabsContent>
          </Tabs>
        </>)}
      </SheetContent>
    </Sheet>
  );
};
