package com.amts.agent.transport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** REST transport to the backend (/api/agent/*). Authenticated by the pairing token. */
public class BackendClient {
    public static final ObjectMapper JSON = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private final String base;
    private final String token;

    public static class BackendException extends IOException {
        public final int status;

        BackendException(int status, String body) {
            super("Backend returned " + status + ": " + body);
            this.status = status;
        }
    }

    public BackendClient(String backendUrl, String token) {
        this.base = backendUrl + "/api/agent";
        this.token = token;
    }

    public JsonNode post(String path, Object body) throws IOException, InterruptedException {
        HttpRequest req = HttpRequest.newBuilder(URI.create(base + path)).timeout(Duration.ofSeconds(20))
                .header("Content-Type", "application/json").header("X-Agent-Token", token)
                .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))).build();
        return send(req);
    }

    public JsonNode heartbeat(Map<String, Object> body) throws IOException, InterruptedException {
        return post("/heartbeat", body);
    }

    public void commandResult(String id, String status, String error) throws IOException, InterruptedException {
        post("/commands/" + id + "/result", error == null ? Map.of("status", status) : Map.of("status", status, "error", error));
    }

    public JsonNode sessionState(String sessionId, Map<String, Object> body) throws IOException, InterruptedException {
        return post("/sessions/" + sessionId + "/state", body);
    }

    public JsonNode replayStatus(String runId, Map<String, Object> body) throws IOException, InterruptedException {
        return post("/replays/" + runId + "/status", body);
    }

    public JsonNode events(String sessionId, List<Map<String, Object>> events) throws IOException, InterruptedException {
        return post("/sessions/" + sessionId + "/events", Map.of("events", events));
    }

    public JsonNode uploadScreen(String sessionId, Map<String, Object> metadata, String xml, byte[] png)
            throws IOException, InterruptedException {
        String boundary = "amts" + UUID.randomUUID();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        part(out, boundary, "metadata", null, "application/json", JSON.writeValueAsBytes(metadata));
        if (xml != null) part(out, boundary, "hierarchy", "hierarchy.xml", "application/xml", xml.getBytes(StandardCharsets.UTF_8));
        if (png != null) part(out, boundary, "screenshot", "screenshot.png", "image/png", png);
        out.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        HttpRequest req = HttpRequest.newBuilder(URI.create(base + "/sessions/" + sessionId + "/screens"))
                .timeout(Duration.ofSeconds(60)).header("X-Agent-Token", token)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(out.toByteArray())).build();
        return send(req);
    }

    private static void part(ByteArrayOutputStream out, String boundary, String name, String filename, String type,
                             byte[] data) throws IOException {
        String header = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\""
                + (filename != null ? "; filename=\"" + filename + "\"" : "") + "\r\nContent-Type: " + type + "\r\n\r\n";
        out.write(header.getBytes(StandardCharsets.UTF_8));
        out.write(data);
        out.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    private JsonNode send(HttpRequest req) throws IOException, InterruptedException {
        HttpResponse<String> r = http.send(req, HttpResponse.BodyHandlers.ofString());
        if (r.statusCode() >= 300) throw new BackendException(r.statusCode(), r.body());
        return r.body().isEmpty() ? JSON.createObjectNode() : JSON.readTree(r.body());
    }
}
