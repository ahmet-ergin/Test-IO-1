import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Smartphone, Package } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useApp } from "@/context/AppContext";
import { http, errMsg } from "@/lib/api";
import { KV } from "@/components/common";

export const useReplayTarget = (sessionId) => {
  const [target, setTarget] = useState(null);
  const load = useCallback(() => {
    if (!sessionId || document.hidden) return;
    http.get(`/sessions/${sessionId}/replay-target`).then((r) => setTarget(r.data)).catch(() => setTarget(null));
  }, [sessionId]);
  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, [load]);
  return [target, load];
};

const ConfirmReplay = ({ target, open, onCancel, onConfirm, busy }) => {
  const { t } = useApp();
  const d = target?.device || {};
  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent data-testid="replay-confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{t("replay_confirm_title")}</AlertDialogTitle>
          <AlertDialogDescription>{t("replay_confirm_text")}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid grid-cols-2 gap-4 rounded-md border border-border bg-muted/30 p-4">
          <div className="flex gap-2"><Smartphone className="mt-1 h-4 w-4 text-primary" /><KV label={t("replay_device")} testId="replay-confirm-device" value={`${d.manufacturer || ""} ${d.model || ""}`.trim() || d.serial} /></div>
          <KV label={t("col_serial")} testId="replay-confirm-serial" value={d.serial} />
          <div className="flex gap-2"><Package className="mt-1 h-4 w-4 text-primary" /><KV label={t("replay_app")} testId="replay-confirm-package" value={target?.appPackage} /></div>
          <KV label={t("replay_activity")} testId="replay-confirm-activity" value={target?.appActivity?.replace(target?.appPackage, "")} />
          <KV label={t("replay_steps")} testId="replay-confirm-steps" value={`${target?.stepCount} × TAP`} />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="replay-confirm-cancel">{t("btn_cancel")}</AlertDialogCancel>
          <AlertDialogAction data-testid="replay-confirm-start" disabled={busy} onClick={onConfirm}>
            <Play className="mr-2 h-4 w-4" />{t("btn_replay_start")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export const ReplayButton = ({ sessionId, compact = false, testId = "replay-button" }) => {
  const { t } = useApp();
  const nav = useNavigate();
  const [target, reload] = useReplayTarget(sessionId);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ok = !!target?.compatible;
  const errKey = `replay_err_${target?.error?.code}`;
  const reason = target?.error ? (t(errKey) !== errKey ? t(errKey) : target.error.message) : t("replay_checking");
  const start = async () => {
    setBusy(true);
    try {
      const { data } = await http.post(`/sessions/${sessionId}/replays`);
      setOpen(false);
      nav(`/replays/${data.id}`);
    } catch (e) { toast.error(errMsg(e)); reload(); } finally { setBusy(false); }
  };
  return (
    <>
      <span title={ok ? t("btn_replay") : reason} data-testid={`${testId}-wrapper`}>
        <Button data-testid={testId} size={compact ? "icon" : "sm"} variant={compact ? "ghost" : "default"} disabled={!ok}
          onClick={() => setOpen(true)} className={compact ? "" : "gap-2"}>
          <Play className={`h-4 w-4 ${compact && ok ? "text-emerald-500" : ""}`} />{!compact && t("btn_replay")}
        </Button>
      </span>
      {!compact && !ok && target?.error && <span data-testid={`${testId}-disabled-reason`} className="max-w-xs text-xs text-muted-foreground">{reason}</span>}
      <ConfirmReplay target={target} open={open} busy={busy} onCancel={() => setOpen(false)} onConfirm={(e) => { e.preventDefault(); start(); }} />
    </>
  );
};
