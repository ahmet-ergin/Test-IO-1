package com.amts.agent.config;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/** Loads agent.properties; environment variables (AMTS_*) override file values. */
public final class AgentConfig {
    public final String backendUrl;
    public final String agentToken;
    public final String adbPath;
    public final long heartbeatMs;
    public final String agentName;
    public final String companionPackage;
    public final String appiumUrl;
    public final long replayFindTimeoutMs;
    public final long appiumSessionTimeoutMs;
    public final java.util.Set<String> replayAllowedPackages;

    private AgentConfig(Properties p) {
        this.backendUrl = trimSlash(required(p, "backend.url", "AMTS_BACKEND_URL"));
        this.agentToken = required(p, "agent.token", "AMTS_AGENT_TOKEN");
        this.adbPath = value(p, "adb.path", "AMTS_ADB_PATH", "adb");
        this.heartbeatMs = Long.parseLong(value(p, "heartbeat.ms", "AMTS_HEARTBEAT_MS", "1000"));
        this.agentName = value(p, "agent.name", "AMTS_AGENT_NAME", hostName());
        this.companionPackage = value(p, "companion.package", "AMTS_COMPANION_PACKAGE", "com.amts.companion");
        this.appiumUrl = trimSlash(value(p, "appium.url", "AMTS_APPIUM_URL", "http://127.0.0.1:4723"));
        this.replayFindTimeoutMs = Long.parseLong(value(p, "replay.find.timeout.ms", "AMTS_REPLAY_FIND_TIMEOUT_MS", "10000"));
        this.appiumSessionTimeoutMs = Long.parseLong(value(p, "appium.session.timeout.ms", "AMTS_APPIUM_SESSION_TIMEOUT_MS", "120000"));
        this.replayAllowedPackages = java.util.Set.of(value(p, "replay.allowed.packages", "AMTS_REPLAY_ALLOWED_PACKAGES",
                "com.amts.sampleapp").split("\\s*,\\s*"));
    }

    public static AgentConfig load(Path file) throws IOException {
        Properties p = new Properties();
        if (Files.exists(file)) {
            try (InputStream in = Files.newInputStream(file)) {
                p.load(in);
            }
        }
        return new AgentConfig(p);
    }

    private static String value(Properties p, String key, String env, String def) {
        String e = System.getenv(env);
        if (e != null && !e.isBlank()) return e.trim();
        String v = p.getProperty(key);
        return v == null || v.isBlank() ? def : v.trim();
    }

    private static String required(Properties p, String key, String env) {
        String v = value(p, key, env, null);
        if (v == null) throw new IllegalStateException("Missing required config '" + key + "' (or env " + env + ")");
        return v;
    }

    private static String trimSlash(String s) {
        return s.endsWith("/") ? s.substring(0, s.length() - 1) : s;
    }

    private static String hostName() {
        try {
            return java.net.InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            return "recorder-agent";
        }
    }
}
