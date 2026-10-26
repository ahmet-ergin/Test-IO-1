package com.amts.agent.replay;

import com.amts.agent.replay.AppiumClient.AppiumException;
import com.amts.agent.transport.BackendClient;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

/** Executes a START_REPLAY command: one Appium session, TAP steps only, unique-locator clicks, no coordinates. */
public class ReplayRunner {
    private static final Logger LOG = Logger.getLogger(ReplayRunner.class.getName());
    static final List<String> LOCATOR_ORDER = List.of("RESOURCE_ID", "UIAUTOMATOR", "XPATH");
    private static final Map<String, String> USING = Map.of(
            "RESOURCE_ID", "id", "UIAUTOMATOR", "-android uiautomator", "XPATH", "xpath");

    private final AppiumClient appium;
    private final BackendClient backend;
    private final String agentId;
    private final Set<String> allowedPackages;
    private final long findTimeoutMs;
    private final long pollMs;

    public ReplayRunner(AppiumClient appium, BackendClient backend, String agentId, Set<String> allowedPackages,
                        long findTimeoutMs, long pollMs) {
        this.appium = appium;
        this.backend = backend;
        this.agentId = agentId;
        this.allowedPackages = allowedPackages;
        this.findTimeoutMs = findTimeoutMs;
        this.pollMs = pollMs;
    }

    static class StepFailure extends Exception {
        final String code;
        final List<Map<String, Object>> attempts;

        StepFailure(String code, String message, List<Map<String, Object>> attempts) {
            super(message);
            this.code = code;
            this.attempts = attempts;
        }
    }

    /** Fails a run before anything is executed (e.g. recording active). */
    public void reject(JsonNode payload, String code, String message) {
        report(payload.path("runId").asText(), "FAILED", err(code, message), List.of());
    }

    /** @return true when every step passed. */
    public boolean run(JsonNode payload) {
        String runId = payload.path("runId").asText();
        String precheck = precheck(payload);
        if (precheck != null) {
            String[] p = precheck.split("\\|", 2);
            reject(payload, p[0], p[1]);
            return false;
        }
        if (!report(runId, "RUNNING", null, List.of())) return false;
        List<Map<String, Object>> results = new ArrayList<>();
        Map<String, Object> runError = null;
        String sessionId = null;
        boolean passed = false;
        try {
            sessionId = appium.createSession(capabilities(payload));
            LOG.info("Replay " + runId + ": Appium session created");
            passed = true;
            for (JsonNode step : payload.path("steps")) {
                Map<String, Object> r = runStep(sessionId, step);
                results.add(r);
                if (!"PASSED".equals(r.get("status"))) {
                    passed = false;
                    break;
                }
            }
        } catch (AppiumException e) {
            passed = false;
            runError = err(e.code, e.getMessage());
        } catch (RuntimeException e) {
            passed = false;
            runError = err("AGENT_ERROR", "Unexpected agent error: " + AppiumClient.trim(String.valueOf(e.getMessage())));
        } finally {
            if (sessionId != null) {
                try {
                    appium.deleteSession(sessionId);
                    LOG.info("Replay " + runId + ": Appium session deleted");
                } catch (AppiumException e) {
                    LOG.warning("Replay " + runId + ": could not delete Appium session: " + e.code);
                }
            }
        }
        LOG.info("Replay " + runId + " " + (passed ? "PASSED" : "FAILED"));
        report(runId, passed ? "PASSED" : "FAILED", passed ? null : runError, results);
        return passed;
    }

    String precheck(JsonNode p) {
        if (p.path("runId").asText("").isEmpty()) return "INVALID_COMMAND|Missing runId.";
        if (p.path("deviceSerial").asText("").isEmpty()) return "INVALID_COMMAND|Missing deviceSerial.";
        if (!allowedPackages.contains(p.path("appPackage").asText()))
            return "APP_NOT_ALLOWED|Agent only replays " + allowedPackages + " in this MVP.";
        if (p.path("appActivity").asText("").isEmpty()) return "INVALID_COMMAND|Missing appActivity.";
        if (!p.path("steps").isArray() || p.path("steps").size() == 0) return "NO_STEPS|No steps to replay.";
        for (JsonNode s : p.path("steps")) {
            if (!"TAP".equals(s.path("action").asText()))
                return "UNSUPPORTED_ACTION|Step #" + s.path("order").asInt() + " action " + s.path("action").asText()
                        + " is not supported (TAP only). Nothing was executed.";
        }
        return null;
    }

    static Map<String, Object> capabilities(JsonNode p) {
        Map<String, Object> c = new LinkedHashMap<>();
        c.put("platformName", "Android");
        c.put("appium:automationName", "UiAutomator2");
        c.put("appium:udid", p.path("deviceSerial").asText());
        c.put("appium:appPackage", p.path("appPackage").asText());
        c.put("appium:appActivity", p.path("appActivity").asText());
        c.put("appium:noReset", true);
        c.put("appium:newCommandTimeout", 60);
        return c;
    }

    static List<String[]> orderedLocators(JsonNode step) {
        List<String[]> out = new ArrayList<>();
        for (String strategy : LOCATOR_ORDER) {
            for (JsonNode l : step.path("locators")) {
                if (strategy.equals(l.path("strategy").asText()) && !l.path("value").asText("").isEmpty()) {
                    out.add(new String[]{strategy, l.path("value").asText()});
                    break;
                }
            }
        }
        return out;
    }

    Map<String, Object> runStep(String sessionId, JsonNode step) throws AppiumException {
        long t0 = System.currentTimeMillis();
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("stepId", step.path("stepId").asText());
        int order = step.path("order").asInt();
        try {
            String[] used = locateAndClick(sessionId, orderedLocators(step), r);
            r.put("status", "PASSED");
            r.put("locator", Map.of("strategy", used[0], "value", used[1]));
            LOG.info("Replay step #" + order + " PASSED via " + used[0]);
        } catch (StepFailure f) {
            r.put("status", "FAILED");
            r.put("error", err(f.code, f.getMessage()));
            r.put("attempts", f.attempts);
            LOG.info("Replay step #" + order + " FAILED: " + f.code);
        }
        r.put("durationMs", System.currentTimeMillis() - t0);
        return r;
    }

    private String[] locateAndClick(String sessionId, List<String[]> locators, Map<String, Object> r)
            throws StepFailure, AppiumException {
        if (locators.isEmpty())
            throw new StepFailure("NO_REPLAYABLE_LOCATOR", "Step has no RESOURCE_ID, UIAUTOMATOR or XPATH locator.", List.of());
        long deadline = System.currentTimeMillis() + findTimeoutMs;
        Map<String, Map<String, Object>> attempts = new LinkedHashMap<>();
        while (true) {
            for (String[] loc : locators) {
                List<String> ids;
                try {
                    ids = appium.findElements(sessionId, USING.get(loc[0]), loc[1]);
                    attempts.put(loc[0], attempt(loc[0], ids.size(), null));
                } catch (AppiumException e) {
                    if (!"FIND_FAILED".equals(e.code)) throw e;
                    attempts.put(loc[0], attempt(loc[0], null, e.getMessage()));
                    continue;
                }
                if (ids.size() > 1)
                    throw new StepFailure("AMBIGUOUS_LOCATOR", loc[0] + " locator matched " + ids.size()
                            + " elements; refusing to click an ambiguous target.", new ArrayList<>(attempts.values()));
                if (ids.size() == 1) {
                    try {
                        appium.click(sessionId, ids.get(0));
                    } catch (AppiumException e) {
                        throw new StepFailure("CLICK_FAILED", "Click via " + loc[0] + " failed: " + e.getMessage(),
                                new ArrayList<>(attempts.values()));
                    }
                    r.put("attempts", new ArrayList<>(attempts.values()));
                    return loc;
                }
            }
            if (System.currentTimeMillis() >= deadline) {
                throw new StepFailure("ELEMENT_NOT_FOUND", "No locator matched within " + findTimeoutMs + " ms (tried "
                        + String.join(", ", attempts.keySet()) + ").", new ArrayList<>(attempts.values()));
            }
            sleep();
        }
    }

    private static Map<String, Object> attempt(String strategy, Integer count, String error) {
        Map<String, Object> a = new LinkedHashMap<>();
        a.put("strategy", strategy);
        a.put("matchCount", count);
        if (error != null) a.put("error", error);
        return a;
    }

    private void sleep() throws StepFailure {
        try {
            Thread.sleep(pollMs);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new StepFailure("INTERRUPTED", "Replay interrupted.", List.of());
        }
    }

    private static Map<String, Object> err(String code, String message) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("code", code);
        e.put("message", message);
        return e;
    }

    private boolean report(String runId, String status, Map<String, Object> error, List<Map<String, Object>> steps) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("agentId", agentId);
        body.put("status", status);
        if (error != null) body.put("error", error);
        body.put("steps", steps);
        for (int i = 1; i <= 3; i++) {
            try {
                backend.replayStatus(runId, body);
                return true;
            } catch (BackendClient.BackendException e) {
                LOG.warning("Replay " + runId + " status " + status + " rejected by backend: HTTP " + e.status);
                return false;
            } catch (Exception e) {
                LOG.warning("Replay " + runId + " status report attempt " + i + " failed: " + e.getClass().getSimpleName());
                try {
                    Thread.sleep(1000L * i);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
        }
        return false;
    }
}
