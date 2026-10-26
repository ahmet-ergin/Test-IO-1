package com.amts.agent;

import com.amts.agent.replay.AppiumClient;
import com.amts.agent.replay.ReplayRunner;
import com.amts.agent.transport.BackendClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.junit.jupiter.api.Assertions.*;

/** ReplayRunner against an in-process fake Appium + fake backend (real HTTP, no device). */
class ReplayRunnerTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private HttpServer server;
    private final List<String> calls = new CopyOnWriteArrayList<>();
    private final List<JsonNode> reports = new CopyOnWriteArrayList<>();
    /** "using|value" -> number of matches */
    private final Map<String, Integer> matches = new ConcurrentHashMap<>();
    private volatile boolean failSession;
    private ReplayRunner runner;

    @BeforeEach
    void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", ex -> {
            String path = ex.getRequestURI().getPath(), method = ex.getRequestMethod();
            String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            calls.add(method + " " + path);
            String resp;
            int code = 200;
            if (path.startsWith("/api/agent/replays/")) {
                reports.add(JSON.readTree(body));
                resp = "{}";
            } else if (path.equals("/session") && method.equals("POST")) {
                if (failSession) {
                    code = 500;
                    resp = "{\"value\":{\"error\":\"session not created\",\"message\":\"Device REPLAY-1 not found\\nstack\"}}";
                } else resp = "{\"value\":{\"sessionId\":\"s1\",\"capabilities\":{}}}";
            } else if (path.endsWith("/elements")) {
                JsonNode b = JSON.readTree(body);
                int n = matches.getOrDefault(b.path("using").asText() + "|" + b.path("value").asText(), 0);
                StringBuilder sb = new StringBuilder("{\"value\":[");
                for (int i = 0; i < n; i++) sb.append(i > 0 ? "," : "").append("{\"element-6066-11e4-a52e-4f735466cecf\":\"e").append(i).append("\"}");
                resp = sb.append("]}").toString();
            } else resp = "{\"value\":null}";
            byte[] out = resp.getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(code, out.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(out);
            }
        });
        server.start();
        String url = "http://127.0.0.1:" + server.getAddress().getPort();
        AppiumClient appium = new AppiumClient(url, Duration.ofSeconds(2), Duration.ofSeconds(5), Duration.ofSeconds(5));
        runner = new ReplayRunner(appium, new BackendClient(url, "t"), "agent-1", Set.of("com.amts.sampleapp"), 300, 50);
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private JsonNode payload(String action) throws Exception {
        return JSON.readTree("{\"runId\":\"r1\",\"deviceSerial\":\"REPLAY-1\",\"appPackage\":\"com.amts.sampleapp\","
                + "\"appActivity\":\"com.amts.sampleapp.HomeActivity\",\"steps\":[{\"stepId\":\"st1\",\"order\":1,\"action\":\""
                + action + "\",\"locators\":[{\"strategy\":\"XPATH\",\"value\":\"//b\"},"
                + "{\"strategy\":\"RESOURCE_ID\",\"value\":\"com.amts.sampleapp:id/transferButton\"},"
                + "{\"strategy\":\"UIAUTOMATOR\",\"value\":\"new UiSelector().text(\\\"T\\\")\"}]}]}");
    }

    private JsonNode last() {
        return reports.get(reports.size() - 1);
    }

    @Test
    void tapViaResourceIdPassesAndDeletesSession() throws Exception {
        matches.put("id|com.amts.sampleapp:id/transferButton", 1);
        assertTrue(runner.run(payload("TAP")));
        assertEquals("RUNNING", reports.get(0).path("status").asText());
        assertEquals("PASSED", last().path("status").asText());
        assertEquals("RESOURCE_ID", last().path("steps").get(0).path("locator").path("strategy").asText());
        assertTrue(calls.contains("POST /session/s1/element/e0/click"));
        assertEquals("DELETE /session/s1", calls.get(calls.size() - 2));
    }

    @Test
    void fallsBackToUiAutomatorThenXpath() throws Exception {
        matches.put("xpath|//b", 1);
        assertTrue(runner.run(payload("TAP")));
        assertEquals("XPATH", last().path("steps").get(0).path("locator").path("strategy").asText());
    }

    @Test
    void ambiguousLocatorFailsWithoutClick() throws Exception {
        matches.put("id|com.amts.sampleapp:id/transferButton", 2);
        matches.put("xpath|//b", 1);
        assertFalse(runner.run(payload("TAP")));
        JsonNode st = last().path("steps").get(0);
        assertEquals("AMBIGUOUS_LOCATOR", st.path("error").path("code").asText());
        assertTrue(calls.stream().noneMatch(c -> c.endsWith("/click")));
        assertTrue(calls.contains("DELETE /session/s1"));
    }

    @Test
    void notFoundTimesOutAndDeletesSession() throws Exception {
        assertFalse(runner.run(payload("TAP")));
        assertEquals("ELEMENT_NOT_FOUND", last().path("steps").get(0).path("error").path("code").asText());
        assertTrue(calls.contains("DELETE /session/s1"));
    }

    @Test
    void unsupportedActionRejectedBeforeAppium() throws Exception {
        assertFalse(runner.run(payload("SWIPE")));
        assertEquals(1, reports.size());
        assertEquals("UNSUPPORTED_ACTION", last().path("error").path("code").asText());
        assertTrue(calls.stream().noneMatch(c -> c.contains("/session")));
    }

    @Test
    void sessionCreationFailureReported() throws Exception {
        failSession = true;
        assertFalse(runner.run(payload("TAP")));
        assertEquals("APPIUM_SESSION_FAILED", last().path("error").path("code").asText());
        assertFalse(last().path("error").path("message").asText().contains("stack"));
        assertTrue(calls.stream().noneMatch(c -> c.startsWith("DELETE")));
    }

    @Test
    void appiumUnreachable() throws Exception {
        AppiumClient dead = new AppiumClient("http://127.0.0.1:1", Duration.ofSeconds(1), Duration.ofSeconds(1), Duration.ofSeconds(1));
        String url = "http://127.0.0.1:" + server.getAddress().getPort();
        ReplayRunner r = new ReplayRunner(dead, new BackendClient(url, "t"), "agent-1", Set.of("com.amts.sampleapp"), 100, 50);
        assertFalse(r.run(payload("TAP")));
        assertEquals("APPIUM_UNREACHABLE", last().path("error").path("code").asText());
    }
}
