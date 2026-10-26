import { Lock } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { PageHeader, Panel } from "@/components/common";

const MODULES = {
  locator: {
    nav: "nav_locator", phase: "Phase 2", doc: "docs/architecture/ARCHITECTURE.md §6",
    items: ["Strategies: ACCESSIBILITY_ID, RESOURCE_ID, STABLE_ATTRIBUTES, UIAUTOMATOR, XPATH, COORDINATES",
      "Scoring: uniqueness, stability, readability, platform compatibility, structure dependency, visibility/interactability",
      "LocatorCandidate { strategy, value, confidence, uniqueness, validatedAt, alternatives[] }",
      "On-device validation via Recorder Agent (Phase 1 only checks uniqueness against the captured XML snapshot)"],
  },
  ai: {
    nav: "nav_ai", phase: "Phase 3", doc: "docs/architecture/ARCHITECTURE.md §7",
    items: ["Provider-agnostic AiProvider interface (no hard-coded vendor)",
      "Output separates observedFacts / inferredMeaning / suggestedAssertions / unverifiedAssumptions",
      "Explicit per-request user consent; screenshots and XML are never uploaded automatically",
      "Suggested assertions require user approval; AI never reports verification results"],
  },
  codegen: {
    nav: "nav_codegen", phase: "Phase 4", doc: "docs/architecture/ARCHITECTURE.md §8",
    items: ["AutomationFrameworkAdapter: index existing steps, locators and helpers (read-only)",
      "Match recorded steps to reusable Gauge steps; suggest missing ones",
      "Generate Gauge spec + Java 8-compatible implementations only when required",
      "Output is a reviewable patch/diff — never committed, merged or executed automatically"],
  },
  jira: {
    nav: "nav_jira", phase: "Phase 5", doc: "docs/architecture/ARCHITECTURE.md §9",
    items: ["Separate JiraAdapter and ZephyrScaleAdapter (different APIs)",
      "Credentials stored via secure credential store, never in Git",
      "Test case search, selection, metadata read, flow-to-test-case mapping",
      "Automation status tracking; no write-back in Phase 1"],
  },
};

export default function Planned({ module }) {
  const { t } = useApp();
  const m = MODULES[module];
  return (
    <div data-testid={`planned-page-${module}`}>
      <PageHeader title={t(m.nav)} sub={m.phase}>
        <span data-testid="planned-badge" className="inline-flex items-center gap-1.5 rounded border border-dashed border-border px-2.5 py-1 font-mono text-xs text-muted-foreground">
          <Lock className="h-3 w-3" />{t("planned_badge")}
        </span>
      </PageHeader>
      <Panel className="max-w-3xl border-dashed">
        <p className="mb-4 text-sm text-muted-foreground">{t("planned_intro")}</p>
        <ul className="space-y-2">{m.items.map((i) => <li key={i} className="flex gap-2 text-sm"><span className="font-mono text-primary">›</span>{i}</li>)}</ul>
        <p className="mt-4 font-mono text-xs text-muted-foreground">{m.doc}</p>
      </Panel>
    </div>
  );
}
