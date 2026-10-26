import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard, Smartphone, Video, History, ListChecks, Sliders, Crosshair, Sparkles, Code2, Share2, Moon, Sun, Lock,
} from "lucide-react";
import { useApp } from "@/context/AppContext";
import { StatusBadge } from "@/components/common";

const PHASE1 = [
  ["/", "nav_dashboard", LayoutDashboard, "dashboard"], ["/devices", "nav_devices", Smartphone, "devices"],
  ["/recorder", "nav_recorder", Video, "recorder"], ["/sessions", "nav_sessions", History, "sessions"],
  ["/recorded-steps", "nav_steps", ListChecks, "recorded-steps"], ["/settings", "nav_settings", Sliders, "settings"],
];
const PLANNED = [
  ["/locator-inspector", "nav_locator", Crosshair, "locator-inspector"], ["/ai-analysis", "nav_ai", Sparkles, "ai-analysis"],
  ["/code-generator", "nav_codegen", Code2, "code-generator"], ["/jira-integration", "nav_jira", Share2, "jira-integration"],
];

const NavItem = ({ to, label, Icon, id, planned }) => (
  <NavLink to={to} end={to === "/"} data-testid={`sidebar-link-${id}`}
    className={({ isActive }) => `group flex items-center gap-2.5 rounded px-2.5 py-1.5 text-sm transition-colors duration-150 ${
      isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
    <Icon className="h-4 w-4 shrink-0" />
    <span className="truncate">{label}</span>
    {planned && <Lock className="ml-auto h-3 w-3 opacity-50" />}
  </NavLink>
);

const Sidebar = () => {
  const { t } = useApp();
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card md:flex">
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
        <div className="grid h-7 w-7 place-items-center rounded bg-primary font-mono text-xs font-bold text-primary-foreground">AM</div>
        <div className="leading-tight">
          <div className="font-heading text-sm font-bold">AI Mobile Test Studio</div>
          <div className="font-mono text-[10px] text-muted-foreground">{t("app_subtitle")}</div>
        </div>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto p-3">
        <div className="space-y-0.5">
          <div className="px-2.5 pb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{t("nav_group_phase1")}</div>
          {PHASE1.map(([to, k, I, id]) => <NavItem key={id} to={to} label={t(k)} Icon={I} id={id} />)}
        </div>
        <div className="space-y-0.5">
          <div className="px-2.5 pb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{t("nav_group_planned")}</div>
          {PLANNED.map(([to, k, I, id]) => <NavItem key={id} to={to} label={t(k)} Icon={I} id={id} planned />)}
        </div>
      </nav>
    </aside>
  );
};

const Header = () => {
  const { t, status, lang, setLang, theme, setTheme, statusError } = useApp();
  const connected = status?.agentConnected;
  const active = status?.activeSession;
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-4">
      <div className="flex min-w-0 items-center gap-3">
        <span data-testid="header-agent-status"
          className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${connected
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500" : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"}`}>
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500 rec-pulse-green" : "bg-amber-500"}`} />
          {connected ? `${t("agent_connected")} · ${status.agent?.name}` : t("agent_disconnected")}
        </span>
        <span className="hidden truncate font-mono text-xs text-muted-foreground lg:inline" data-testid="header-active-device">
          {t("active_device")}: {status?.activeDeviceSerial || t("no_active_device")}
        </span>
        {active && <StatusBadge status={active.status} testId="header-recording-status" />}
        {statusError && <span className="text-xs text-red-500" data-testid="header-backend-error">API: {statusError}</span>}
      </div>
      <div className="flex items-center gap-1">
        <button data-testid="language-toggle-button" onClick={() => setLang(lang === "tr" ? "en" : "tr")}
          className="rounded px-2 py-1 font-mono text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          {lang === "tr" ? "TR · en" : "EN · tr"}
        </button>
        <button data-testid="theme-toggle-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" aria-label="theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
};

const MobileNav = () => {
  const { t } = useApp();
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-border bg-card px-2 py-1.5 md:hidden">
      {[...PHASE1, ...PLANNED].map(([to, k, , id]) => (
        <NavLink key={id} to={to} end={to === "/"} data-testid={`mobile-link-${id}`}
          className={({ isActive }) => `whitespace-nowrap rounded px-2 py-1 text-xs ${isActive ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}>
          {t(k)}
        </NavLink>
      ))}
    </nav>
  );
};

export default function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <MobileNav />
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 lg:px-10"><Outlet /></main>
      </div>
    </div>
  );
}
