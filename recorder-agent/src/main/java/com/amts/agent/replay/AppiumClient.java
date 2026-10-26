package com.amts.agent.replay;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.ConnectException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpConnectTimeoutException;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Minimal W3C WebDriver client for Appium 2 using java.net.http (no Appium Java Client). */
public class AppiumClient {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String W3C_ELEMENT = "element-6066-11e4-a52e-4f735466cecf";
    private static final int MAX_MSG = 300;

    private final HttpClient http;
    private final String base;
    private final Duration sessionTimeout;
    private final Duration commandTimeout;

    public static class AppiumException extends Exception {
        public final String code;

        public AppiumException(String code, String message) {
            super(message);
            this.code = code;
        }
    }

    public AppiumClient(String baseUrl, Duration connectTimeout, Duration sessionTimeout, Duration commandTimeout) {
        this.base = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.http = HttpClient.newBuilder().connectTimeout(connectTimeout).build();
        this.sessionTimeout = sessionTimeout;
        this.commandTimeout = commandTimeout;
    }

    public String createSession(Map<String, Object> capabilities) throws AppiumException {
        Map<String, Object> body = Map.of("capabilities", Map.of("alwaysMatch", capabilities, "firstMatch", List.of(Map.of())));
        JsonNode v = call("POST", "/session", body, sessionTimeout, "APPIUM_SESSION_FAILED");
        String id = v.path("sessionId").asText("");
        if (id.isEmpty()) throw new AppiumException("APPIUM_SESSION_FAILED", "Appium did not return a session id.");
        return id;
    }

    /** Returns element ids matching the locator (possibly empty). */
    public List<String> findElements(String sessionId, String using, String value) throws AppiumException {
        JsonNode v = call("POST", "/session/" + sessionId + "/elements", Map.of("using", using, "value", value),
                commandTimeout, "FIND_FAILED");
        List<String> ids = new ArrayList<>();
        for (JsonNode e : v) {
            String id = e.path(W3C_ELEMENT).asText(e.path("ELEMENT").asText(""));
            if (!id.isEmpty()) ids.add(id);
        }
        return ids;
    }

    public void click(String sessionId, String elementId) throws AppiumException {
        call("POST", "/session/" + sessionId + "/element/" + elementId + "/click", Map.of(), commandTimeout, "CLICK_FAILED");
    }

    public void deleteSession(String sessionId) throws AppiumException {
        call("DELETE", "/session/" + sessionId, null, commandTimeout, "APPIUM_DELETE_FAILED");
    }

    private JsonNode call(String method, String path, Object body, Duration timeout, String failCode) throws AppiumException {
        HttpResponse<String> r;
        try {
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(base + path)).timeout(timeout)
                    .header("Content-Type", "application/json; charset=utf-8");
            b = body == null ? b.method(method, HttpRequest.BodyPublishers.noBody())
                    : b.method(method, HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body)));
            r = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
        } catch (ConnectException | HttpConnectTimeoutException e) {
            throw new AppiumException("APPIUM_UNREACHABLE", "Appium server not reachable at " + base
                    + ". Start Appium 2 locally (e.g. `appium`) and retry.");
        } catch (HttpTimeoutException e) {
            throw new AppiumException("APPIUM_TIMEOUT", "Appium did not respond within " + timeout.toSeconds() + " s (" + method + " " + stripSession(path) + ").");
        } catch (IOException e) {
            throw new AppiumException("APPIUM_UNREACHABLE", "Appium request failed: " + trim(e.getMessage()));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new AppiumException("INTERRUPTED", "Replay interrupted.");
        }
        JsonNode root;
        try {
            root = r.body() == null || r.body().isBlank() ? JSON.createObjectNode() : JSON.readTree(r.body());
        } catch (IOException e) {
            throw new AppiumException(failCode, "Appium returned non-JSON response (HTTP " + r.statusCode() + ").");
        }
        JsonNode v = root.path("value");
        if (r.statusCode() >= 300 || (v.isObject() && v.has("error"))) {
            String err = v.path("error").asText("http " + r.statusCode());
            throw new AppiumException(failCode, err + ": " + trim(v.path("message").asText("")));
        }
        return v;
    }

    private static String stripSession(String path) {
        return path.replaceAll("/session/[^/]+", "/session/{id}").replaceAll("/element/[^/]+", "/element/{id}");
    }

    static String trim(String s) {
        if (s == null) return "";
        String first = s.split("\n", 2)[0];
        return first.length() > MAX_MSG ? first.substring(0, MAX_MSG) + "…" : first;
    }
}
