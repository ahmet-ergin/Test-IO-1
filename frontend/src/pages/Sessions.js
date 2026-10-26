import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, FlaskConical, ListChecks, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useApp } from "@/context/AppContext";
import { http, errMsg, fmtDuration, fmtTime, downloadExport } from "@/lib/api";
import { PageHeader, Panel, StatusBadge, DemoBadge, EmptyState, Tag } from "@/components/common";

export default function Sessions() {
  const { t, refreshStatus } = useApp();
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [toDelete, setToDelete] = useState(null);
  const load = useCallback(() => http.get("/sessions").then((r) => setItems(r.data)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { load(); }, [load]);

  const createDemo = async () => {
    try { const { data } = await http.post("/demo/sessions"); toast.success(data.name); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const del = async () => {
    const id = toDelete; setToDelete(null);
    try { await http.delete(`/sessions/${id}`); load(); refreshStatus(); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div data-testid="sessions-page">
      <PageHeader title={t("sessions_title")} sub={t("sessions_sub")}>
        <Button data-testid="sessions-create-demo-button" variant="outline" size="sm" onClick={createDemo}>
          <FlaskConical className="mr-2 h-4 w-4 text-amber-500" />{t("btn_demo")}
        </Button>
      </PageHeader>
      <Panel testId="sessions-table-panel">
        {items.length === 0 ? <EmptyState text={t("sessions_empty")} testId="sessions-empty" /> : (
          <Table>
            <TableHeader><TableRow>
              {["col_name", "col_device", "col_package", "col_status", "col_events", "col_duration", "col_created", "col_actions"].map((k) => <TableHead key={k}>{t(k)}</TableHead>)}
            </TableRow></TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.id} data-testid={`session-row-${s.id}`}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium">{s.demo && <DemoBadge testId={`session-demo-badge-${s.id}`} />}{s.name}</div>
                    <div className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">{s.id.slice(0, 8)}{s.saved && <Tag tone="blue">SAVED</Tag>}</div>
                  </TableCell>
                  <TableCell className="text-xs">{s.device?.model}<div className="font-mono text-[10px] text-muted-foreground">{s.device?.serial}</div></TableCell>
                  <TableCell className="font-mono text-xs">{s.package_name || "—"}</TableCell>
                  <TableCell><StatusBadge status={s.status} testId={`session-status-${s.id}`} /></TableCell>
                  <TableCell className="font-mono text-xs">{s.event_count}</TableCell>
                  <TableCell className="font-mono text-xs">{fmtDuration(s.duration_ms)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{fmtTime(s.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" title={t("nav_steps")} data-testid={`session-open-${s.id}`} onClick={() => nav(`/recorded-steps/${s.id}`)}><ListChecks className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" title={t("btn_export")} data-testid={`session-export-${s.id}`} onClick={() => downloadExport(s.id).catch((e) => toast.error(errMsg(e)))}><Download className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" title={t("btn_delete")} data-testid={`session-delete-${s.id}`} onClick={() => setToDelete(s.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent data-testid="session-delete-dialog">
          <AlertDialogHeader><AlertDialogTitle>{t("btn_delete")}</AlertDialogTitle><AlertDialogDescription>{t("confirm_delete")}</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="session-delete-cancel">{t("btn_cancel")}</AlertDialogCancel>
            <AlertDialogAction data-testid="session-delete-confirm" onClick={del}>{t("btn_delete")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
