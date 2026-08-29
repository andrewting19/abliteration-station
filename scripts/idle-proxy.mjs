#!/usr/bin/env node

import fs from "node:fs";
import http from "node:http";
import crypto from "node:crypto";
import { spawn } from "node:child_process";

const listenHost = process.env.ABLITERATION_STATION_PROXY_HOST ?? "127.0.0.1";
const listenPort = Number(process.env.ABLITERATION_STATION_PROXY_PORT ?? "17071");
const idleSeconds = Number(process.env.ABLITERATION_STATION_IDLE_SECONDS ?? "600");
const testMode = process.env.ABLITERATION_STATION_TEST_MODE === "1";
const idlePollMs = Number(process.env.ABLITERATION_STATION_IDLE_POLL_MS ?? "15000");
const routeFile = process.env.ABLITERATION_STATION_ROUTE_FILE ?? "/run/abliteration-station/route.json";
const activityFile = process.env.ABLITERATION_STATION_ACTIVITY_FILE ?? "/run/abliteration-station/activity.json";
const stopCommand = process.env.ABLITERATION_STATION_STOP_COMMAND ?? "/usr/local/bin/abliteration-station";
const ensureCommand = process.env.ABLITERATION_STATION_ENSURE_COMMAND ?? "/usr/local/bin/abliteration-station";
const configFile = process.env.ABLITERATION_STATION_CONFIG ?? "/etc/abliteration-station/config.json";
const metricsFile = process.env.ABLITERATION_STATION_METRICS_FILE ?? "/var/lib/abliteration-station/metrics/requests.jsonl";

if (!Number.isFinite(idleSeconds) || idleSeconds < (testMode ? 1 : 60)) {
  throw new Error(`ABLITERATION_STATION_IDLE_SECONDS must be at least ${testMode ? 1 : 60}`);
}
if (!Number.isFinite(idlePollMs) || idlePollMs < (testMode ? 100 : 1000)) {
  throw new Error("ABLITERATION_STATION_IDLE_POLL_MS is too small");
}

fs.mkdirSync(new URL(".", `file://${activityFile}`).pathname, { recursive: true });
fs.mkdirSync(new URL(".", `file://${metricsFile}`).pathname, { recursive: true });
let activeRequests = 0;
let lastActivityMs = Date.now();
let stoppedActivityMs = null;
let inhibitUntilMs = 0;
let stopInFlight = false;
let stopPromise = null;
let ensureInFlight = null;
let lastWakeError = null;

function readRoute() {
  return JSON.parse(fs.readFileSync(routeFile, "utf8"));
}

function writeState() {
  const now = Date.now();
  const temporary = `${activityFile}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify({
    active_requests: activeRequests,
    last_activity_unix_ms: lastActivityMs,
    idle_seconds: Math.max(0, Math.floor((now - lastActivityMs) / 1000)),
    idle_limit_seconds: idleSeconds,
    inhibit_until_unix_ms: inhibitUntilMs || null,
    stopped_for_activity_unix_ms: stoppedActivityMs,
    wake_in_flight: ensureInFlight !== null,
    last_wake_error: lastWakeError,
    route: fs.existsSync(routeFile) ? readRoute() : null,
  })}\n`, { mode: 0o600 });
  fs.renameSync(temporary, activityFile);
}

function touch() {
  lastActivityMs = Date.now();
  stoppedActivityMs = null;
  writeState();
}

function stopIdleProvider(snapshot) {
  stopInFlight = true;
  const child = spawn(stopCommand, ["--config", configFile, "stop"], {
    stdio: ["ignore", "inherit", "inherit"],
  });
  stopPromise = new Promise((resolve) => {
    child.once("exit", resolve);
    child.once("error", resolve);
  });
  child.on("exit", (code) => {
    if (code === 0) stoppedActivityMs = snapshot;
    stopInFlight = false;
    stopPromise = null;
    writeState();
  });
  child.on("error", (error) => {
    console.error(`Idle stop failed: ${error.message}`);
    stopInFlight = false;
    stopPromise = null;
  });
}

async function ensureRoute() {
  try {
    return readRoute();
  } catch {
    // Continue to the serialized wake path.
  }
  if (ensureInFlight === null) {
    ensureInFlight = (async () => {
      if (stopPromise !== null) await stopPromise;
      const child = spawn(ensureCommand, ["--config", configFile, "ensure"], {
        stdio: ["ignore", "ignore", "inherit"],
      });
      const code = await new Promise((resolve, reject) => {
        child.once("exit", resolve);
        child.once("error", reject);
      });
      if (code !== 0) throw new Error(`model wake command exited with status ${code}`);
      const route = readRoute();
      lastWakeError = null;
      return route;
    })().catch((error) => {
      lastWakeError = error.message;
      throw error;
    }).finally(() => {
      ensureInFlight = null;
      writeState();
    });
    writeState();
  }
  return ensureInFlight;
}

setInterval(() => {
  const now = Date.now();
  writeState();
  if (
    now < inhibitUntilMs ||
    activeRequests !== 0 ||
    now - lastActivityMs < idleSeconds * 1000 ||
    stoppedActivityMs === lastActivityMs ||
    stopInFlight
  ) return;
  stopIdleProvider(lastActivityMs);
}, idlePollMs).unref();

const server = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url?.startsWith("/lifecycle/inhibit")) {
    const requested = Number(new URL(req.url, "http://localhost").searchParams.get("seconds") ?? "3600");
    inhibitUntilMs = Date.now() + Math.min(7200, Math.max(60, requested)) * 1000;
    touch();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(`${JSON.stringify({ inhibit_until_unix_ms: inhibitUntilMs })}\n`);
    return;
  }
  if (req.method === "POST" && req.url === "/lifecycle/release") {
    inhibitUntilMs = 0;
    touch();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end("{\"released\":true}\n");
    return;
  }
  if (req.url === "/healthz") {
    writeState();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(fs.readFileSync(activityFile));
    return;
  }

  const isInference = req.method === "POST" && [
    "/v1/chat/completions", "/v1/responses", "/completion",
  ].includes(new URL(req.url ?? "/", "http://localhost").pathname);
  if (isInference) {
    activeRequests += 1;
    touch();
  }
  const metric = isInference ? {
    schema_version: 1,
    request_id: crypto.randomUUID(),
    started_at: new Date().toISOString(),
    endpoint: new URL(req.url ?? "/", "http://localhost").pathname,
    wake_required: false,
    wake_seconds: null,
    upstream_headers_seconds: null,
    first_response_byte_seconds: null,
    total_seconds: null,
    status: null,
    response_bytes: 0,
    cancelled: false,
    error: null,
    usage: null,
    timings: null,
  } : null;
  const metricStarted = process.hrtime.bigint();
  const elapsedSeconds = () => Number(process.hrtime.bigint() - metricStarted) / 1e9;
  let metricWritten = false;
  const writeMetric = () => {
    if (metric === null || metricWritten) return;
    metricWritten = true;
    metric.total_seconds = elapsedSeconds();
    fs.appendFileSync(metricsFile, `${JSON.stringify(metric)}\n`, { mode: 0o600 });
  };
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    if (isInference) {
      activeRequests = Math.max(0, activeRequests - 1);
      touch();
    }
    writeMetric();
  };
  let route;
  try {
    const hadRoute = fs.existsSync(routeFile);
    if (metric !== null) metric.wake_required = !hadRoute;
    route = isInference ? await ensureRoute() : readRoute();
    if (metric !== null && !hadRoute) metric.wake_seconds = elapsedSeconds();
  } catch (error) {
    if (metric !== null) {
      metric.status = 503;
      metric.error = `model wake failed: ${error.message}`;
    }
    finish();
    res.writeHead(503, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: { message: `model wake failed: ${error.message}` } }));
    return;
  }
  if (req.destroyed || res.destroyed) {
    finish();
    return;
  }
  const upstream = new URL(route.upstream);
  const upstreamRequest = http.request({
    protocol: upstream.protocol,
    hostname: upstream.hostname,
    port: upstream.port,
    method: req.method,
    path: req.url,
    headers: { ...req.headers, host: upstream.host },
  }, (upstreamResponse) => {
    if (metric !== null) {
      metric.status = upstreamResponse.statusCode ?? 502;
      metric.upstream_headers_seconds = elapsedSeconds();
    }
    res.writeHead(upstreamResponse.statusCode ?? 502, upstreamResponse.headers);
    let eventBuffer = "";
    upstreamResponse.on("data", (chunk) => {
      if (isInference) touch();
      if (metric === null) return;
      if (metric.first_response_byte_seconds === null) metric.first_response_byte_seconds = elapsedSeconds();
      metric.response_bytes += chunk.length;
      eventBuffer += chunk.toString("utf8");
      const lines = eventBuffer.split(/\r?\n/);
      eventBuffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const value = line.slice(5).trim();
        if (!value || value === "[DONE]") continue;
        try {
          const event = JSON.parse(value);
          if (event.usage && typeof event.usage === "object") metric.usage = event.usage;
          if (event.timings && typeof event.timings === "object") metric.timings = event.timings;
        } catch {
          // Ignore partial or non-JSON server events. Never store their content.
        }
      }
    });
    upstreamResponse.on("end", finish);
    upstreamResponse.on("error", finish);
    upstreamResponse.pipe(res);
  });
  upstreamRequest.setTimeout(7_200_000, () => upstreamRequest.destroy(new Error("upstream timed out")));
  upstreamRequest.on("error", (error) => {
    if (metric !== null) metric.error = error.message;
    finish();
    if (!res.destroyed && !res.headersSent) res.writeHead(502, { "Content-Type": "application/json" });
    if (!res.destroyed && !res.writableEnded) res.end(JSON.stringify({ error: { message: error.message } }));
  });
  req.on("aborted", () => {
    if (metric !== null) metric.cancelled = true;
    upstreamRequest.destroy(new Error("client cancelled request"));
  });
  res.on("close", () => {
    if (!finished) {
      if (metric !== null) metric.cancelled = true;
      upstreamRequest.destroy(new Error("client closed response"));
    }
    finish();
  });
  req.pipe(upstreamRequest);
});

server.listen(listenPort, listenHost, () => {
  writeState();
  console.log(`Qwen lifecycle proxy is listening at http://${listenHost}:${listenPort}`);
});
