package com.amts.agent;

import com.amts.agent.adb.AdbClient;
import com.amts.agent.config.AgentConfig;
import com.amts.agent.device.DeviceDiscovery;
import com.amts.agent.replay.AppiumClient;
import com.amts.agent.replay.ReplayRunner;
import com.amts.agent.session.RecordingSession;
import com.amts.agent.transport.BackendClient;
import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Logger;

/** Entry point: heartbeat loop, device discovery and command dispatch. */
public class AgentApp {
    private static final Logger LOG = Logger.getLogger(AgentApp.class.getName());
    public static final String VERSION = "0.1.0";

    private final AgentConfig cfg;
    private final AdbClient adb;
    private final BackendClient backend;
    private final DeviceDiscovery discovery;
    private final ExecutorService commands = Executors.newSingleThreadExecutor();
    private final String agentId;
    private volatile RecordingSession session;
    private final ReplayRunner replay;
    private volatile boolean replayActive;

    AgentApp(AgentConfig cfg) throws Exception {
        this.cfg = cfg;
        this.adb = new AdbClient(cfg.adbPath);
        this.backend = new BackendClient(cfg.backendUrl, cfg.agentToken);
        this.discovery = new DeviceDiscovery(adb, cfg.companionPackage);
        this.agentId = loadAgentId();
        AppiumClient appium = new AppiumClient(cfg.appiumUrl, Duration.ofSeconds(5),
                Duration.ofMillis(cfg.appiumSessionTimeoutMs), Duration.ofSeconds(30));
        this.replay = new ReplayRunner(appium, backend, agentId, cfg.replayAllowedPackages, cfg.replayFindTimeoutMs, 500);
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("java.util.logging.SimpleFormatter.format", "%1$tF %1$tT %4$s %3$s - %5$s%6$s%n");
        if (args.length > 0 && args[0].equals("--diagnose")) {
            Diagnostics.run(args);
            return;
        }
        AgentConfig cfg = AgentConfig.load(Paths.get(args.length > 0 ? args[0] : "agent.properties"));
        LOG.info("AI Mobile Test Studio Recorder Agent " + VERSION + " -> " + cfg.backendUrl);
        new AgentApp(cfg).run();
    }

    private static String loadAgentId() throws Exception {
        Path f = Paths.get(System.getProperty("user.home"), ".amts-agent", "agent-id");
        if (Files.exists(f)) return Files.readString(f).trim();
        Files.createDirectories(f.getParent());
        String id = "agent-" + UUID.randomUUID();
        Files.writeString(f, id);
        return id;
    }

    void run() throws InterruptedException {
        long backoff = cfg.heartbeatMs;
        while (true) {
            try {
                JsonNode resp = backend.heartbeat(heartbeatBody());
                for (JsonNode c : resp.path("commands")) commands.submit(() -> handle(c));
                backoff = cfg.heartbeatMs;
            } catch (BackendClient.BackendException e) {
                LOG.severe(e.getMessage() + (e.status == 401 ? "  -> check agent.token (Settings > Agent pairing)" : ""));
                backoff = Math.min(backoff * 2, 10_000);
            } catch (Exception e) {
                LOG.warning("Backend unreachable: " + e.getMessage());
                backoff = Math.min(backoff * 2, 10_000);
            }
            Thread.sleep(backoff);
        }
    }

    private Map<String, Object> heartbeatBody() {
        Map<String, Object> adbInfo = new LinkedHashMap<>();
        List<Map<String, Object>> devices = new ArrayList<>();
        try {
            adbInfo.put("version", adb.version());
            adbInfo.put("available", true);
            adbInfo.put("simulated", String.valueOf(adbInfo.get("version")).contains("SIMULATED"));
            devices = discovery.discover();
        } catch (Exception e) {
            adbInfo.put("available", false);
            adbInfo.put("error", e.getMessage());
        }
        RecordingSession s = session;
        if (s != null && devices.stream().noneMatch(d -> s.serial.equals(d.get("serial")) && "device".equals(d.get("state")))) {
            LOG.warning("Device " + s.serial + " disconnected; aborting session " + s.id);
            s.abort("Android device disconnected during recording.");
            session = null;
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("agentId", agentId);
        body.put("name", cfg.agentName);
        body.put("version", VERSION);
        body.put("os", System.getProperty("os.name") + " " + System.getProperty("os.version"));
        body.put("javaVersion", System.getProperty("java.version"));
        body.put("adb", adbInfo);
        body.put("devices", devices);
        body.put("activeSessionId", s == null ? null : s.id);
        return body;
    }

    private void handle(JsonNode c) {
        String id = c.path("id").asText(), type = c.path("type").asText(), sid = c.path("session_id").asText(null);
        LOG.info("Command " + type + " session=" + sid);
        try {
            switch (type) {
                case "START_SESSION":
                    if (session != null) throw new IllegalStateException("Agent already recording " + session.id);
                    if (replayActive) throw new IllegalStateException("A replay is running; recording blocked");
                    RecordingSession s = new RecordingSession(sid, c.path("payload"), adb, backend, cfg.companionPackage);
                    session = s;
                    try {
                        s.start();
                    } catch (Exception e) {
                        session = null;
                        s.abort("Recording start failed: " + e.getMessage());
                        throw e;
                    }
                    break;
                case "PAUSE_SESSION":
                    current(sid).pause();
                    break;
                case "RESUME_SESSION":
                    current(sid).resume();
                    break;
                case "STOP_SESSION":
                    RecordingSession cur = current(sid);
                    session = null;
                    cur.stop();
                    break;
                case "START_REPLAY":
                    if (session != null) {
                        replay.reject(c.path("payload"), "RECORDING_ACTIVE", "A recording is active on this agent; replay blocked.");
                        throw new IllegalStateException("Recording active; replay rejected");
                    }
                    replayActive = true;
                    try {
                        replay.run(c.path("payload"));
                    } finally {
                        replayActive = false;
                    }
                    break;
                case "REFRESH_DEVICES":
                    discovery.invalidate();
                    break;
                default:
                    throw new IllegalArgumentException("Unknown command " + type);
            }
            backend.commandResult(id, "DONE", null);
        } catch (Exception e) {
            LOG.warning("Command " + type + " failed: " + e.getMessage());
            try {
                backend.commandResult(id, "FAILED", String.valueOf(e.getMessage()));
            } catch (Exception ignored) {
                LOG.fine("command result not delivered");
            }
        }
    }

    private RecordingSession current(String sid) {
        RecordingSession s = session;
        if (s == null || !s.id.equals(sid)) throw new IllegalStateException("No active recording " + sid + " on this agent");
        return s;
    }
}
