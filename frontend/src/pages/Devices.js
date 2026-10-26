import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Smartphone, Usb, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApp } from "@/context/AppContext";
import { http, errMsg, fmtTime } from "@/lib/api";
import { PageHeader, Panel, Tag, AgentMissing, EmptyState, KV } from "@/components/common";

const StateTag = ({ d, t }) => {
  if (!d.online) return <Tag tone="muted">{t("state_offline")}</Tag>;
  if (d.recording) return <Tag tone="red">REC</Tag>;
  if (d.state === "device") return <Tag tone="green">ONLINE</Tag>;
  return <Tag tone="amber">{d.state.toUpperCase()}</Tag>;
};

const CompanionTag = ({ d, t }) => {
  if (d.companionEnabled) return <Tag tone="green">{t("companion_enabled")}</Tag>;
  if (d.companionInstalled) return <Tag tone="amber">{t("companion_installed_off")}</Tag>;
  if (d.companionInstalled === false) return <Tag tone="muted">{t("companion_missing")}</Tag>;
  return <span className="text-xs text-muted-foreground">—</span>;
};

export default function Devices() {
  const { t, status, refreshStatus } = useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try { setData((await http.get("/devices")).data); } catch (e) { toast.error(errMsg(e)); }
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 3000); return () => clearInterval(id); }, [load]);

  const refresh = async () => {
    setLoading(true);
    try { await http.post("/devices/refresh"); setTimeout(load, 1500); } catch (e) { toast.error(errMsg(e)); }
    setTimeout(() => setLoading(false), 1500);
  };
  const select = async (serial) => {
    try { await http.post(`/devices/${encodeURIComponent(serial)}/select`); refreshStatus(); toast.success(serial); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div data-testid="devices-page">
      <PageHeader title={t("devices_title")} sub={t("devices_sub")}>
        <Button data-testid="device-refresh-button" variant="outline" size="sm" onClick={refresh} disabled={loading || !data?.agentConnected}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />{t("btn_refresh")}
        </Button>
      </PageHeader>
      {data && !data.agentConnected && <AgentMissing />}
      {data?.agentConnected && (
        <div className="space-y-4">
          <Panel title={t("rec_agent")} testId="devices-agent-panel">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
              <KV label="Name" value={data.agent.name} testId="agent-name" />
              <KV label="Version" value={data.agent.version} />
              <KV label="OS" value={data.agent.os} />
              <KV label="Java" value={data.agent.javaVersion} />
              <KV label={t("adb")} testId="adb-status"
                value={data.adb?.available ? <span className="text-emerald-500">{t("adb_available")} · {data.adb.version}</span>
                  : <span className="text-red-500">{t("adb_unavailable")}: {data.adb?.error}</span>} />
            </div>
          </Panel>
          <Panel title={`ADB · ${data.devices.length}`} testId="devices-table-panel">
            {data.devices.length === 0 ? <EmptyState icon={Smartphone} text={t("no_devices")} testId="devices-empty" /> : (
              <Table>
                <TableHeader><TableRow>
                  {["col_model", "col_android", "col_serial", "col_conn", "col_state", "col_companion", "col_actions"].map((k) => <TableHead key={k}>{t(k)}</TableHead>)}
                </TableRow></TableHeader>
                <TableBody>
                  {data.devices.map((d) => {
                    const selected = status?.activeDeviceSerial === d.serial;
                    return (
                      <TableRow key={d.serial} data-testid={`device-row-${d.serial}`}>
                        <TableCell><div className="font-medium">{d.model || t("unavailable")}</div><div className="text-xs text-muted-foreground">{d.manufacturer}</div></TableCell>
                        <TableCell className="font-mono text-xs">{d.androidVersion ? `${d.androidVersion} (API ${d.sdkInt})` : "—"}</TableCell>
                        <TableCell className="font-mono text-xs" data-testid={`device-serial-${d.serial}`}>{d.serial}</TableCell>
                        <TableCell>{d.connectionType === "WIFI" ? <Wifi className="h-4 w-4" /> : <Usb className="h-4 w-4" />}</TableCell>
                        <TableCell><StateTag d={d} t={t} />
                          {d.state === "unauthorized" && <div className="mt-1 max-w-[220px] text-xs text-amber-500">{t("state_unauthorized")}</div>}
                          {!d.online && <div className="mt-1 text-[11px] text-muted-foreground">{fmtTime(d.last_seen)}</div>}
                        </TableCell>
                        <TableCell><CompanionTag d={d} t={t} /></TableCell>
                        <TableCell>
                          <Button size="sm" variant={selected ? "secondary" : "default"} data-testid={`device-select-button-${d.serial}`}
                            disabled={!d.online || d.state !== "device" || selected} onClick={() => select(d.serial)}>
                            {selected ? t("btn_selected") : t("btn_select")}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
