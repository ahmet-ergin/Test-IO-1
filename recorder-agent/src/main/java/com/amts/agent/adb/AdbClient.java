package com.amts.agent.adb;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.logging.Logger;

/** Thin wrapper over the adb binary. All device access goes through here. */
public class AdbClient {
    private static final Logger LOG = Logger.getLogger(AdbClient.class.getName());
    private final String adb;

    public AdbClient(String adbPath) {
        this.adb = adbPath;
    }

    public static final class Result {
        public final int exitCode;
        public final byte[] stdout;
        public final String stderr;

        Result(int exitCode, byte[] stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout = stdout;
            this.stderr = stderr;
        }

        public String text() {
            return new String(stdout, StandardCharsets.UTF_8);
        }

        public boolean ok() {
            return exitCode == 0;
        }
    }

    public Result run(long timeoutMs, String... args) throws IOException {
        List<String> cmd = new ArrayList<>();
        cmd.add(adb);
        cmd.addAll(Arrays.asList(args));
        Process p = new ProcessBuilder(cmd).start();
        CompletableFuture<byte[]> out = CompletableFuture.supplyAsync(() -> readAll(p, false));
        CompletableFuture<byte[]> err = CompletableFuture.supplyAsync(() -> readAll(p, true));
        try {
            if (!p.waitFor(timeoutMs, TimeUnit.MILLISECONDS)) {
                p.destroyForcibly();
                throw new IOException("adb timed out after " + timeoutMs + "ms: " + String.join(" ", args));
            }
            return new Result(p.exitValue(), out.get(2, TimeUnit.SECONDS),
                    new String(err.get(2, TimeUnit.SECONDS), StandardCharsets.UTF_8));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            p.destroyForcibly();
            throw new IOException("interrupted", e);
        } catch (Exception e) {
            if (e instanceof IOException) throw (IOException) e;
            throw new IOException("adb failed: " + e.getMessage(), e);
        }
    }

    public Result shell(String serial, long timeoutMs, String command) throws IOException {
        return run(timeoutMs, "-s", serial, "shell", command);
    }

    public byte[] execOut(String serial, long timeoutMs, String command) throws IOException {
        Result r = run(timeoutMs, "-s", serial, "exec-out", command);
        if (!r.ok()) throw new IOException("exec-out failed: " + r.stderr);
        return r.stdout;
    }

    /** Long-running stream (getevent, logcat). Caller owns the process. */
    public Process stream(String serial, String... args) throws IOException {
        List<String> cmd = new ArrayList<>(Arrays.asList(adb, "-s", serial));
        cmd.addAll(Arrays.asList(args));
        LOG.fine("stream " + cmd);
        Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
        return p;
    }

    public String version() throws IOException {
        Result r = run(5000, "version");
        if (!r.ok()) throw new IOException("adb version failed: " + r.stderr);
        return AdbParsers.parseAdbVersion(r.text());
    }

    private static byte[] readAll(Process p, boolean err) {
        try {
            return (err ? p.getErrorStream() : p.getInputStream()).readAllBytes();
        } catch (IOException e) {
            return new byte[0];
        }
    }
}
