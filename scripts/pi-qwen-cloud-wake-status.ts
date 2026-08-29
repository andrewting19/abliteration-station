import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const STATUS_KEY = "qwen-cloud-wake";
const WIDGET_KEY = "qwen-cloud-wake";
const HEALTH_URL = "http://127.0.0.1:17072/healthz";

export default function (pi: ExtensionAPI) {
  let wakeStartedAt = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  let readyTimer: ReturnType<typeof setTimeout> | undefined;

  const isQwenCloud = (ctx: ExtensionContext) =>
    ctx.model?.provider === "qwen-cloud" || ctx.model?.id === "qwen38-cloud";

  const renderWake = (ctx: ExtensionContext) => {
    const elapsed = Math.max(0, Math.floor((Date.now() - wakeStartedAt) / 1000));
    const message = `Starting Vast and loading Qwen… ${elapsed}s (usually 45–55s)`;
    ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("warning", `◌ ${message}`));
    ctx.ui.setWidget(
      WIDGET_KEY,
      [ctx.ui.theme.fg("warning", `⏳ ${message}`), ctx.ui.theme.fg("dim", "Your prompt is queued and will send automatically.")],
      { placement: "belowEditor" },
    );
    ctx.ui.setWorkingMessage(message);
  };

  const startWakeDisplay = (ctx: ExtensionContext) => {
    if (timer !== undefined) return;
    if (readyTimer !== undefined) clearTimeout(readyTimer);
    readyTimer = undefined;
    wakeStartedAt = Date.now();
    renderWake(ctx);
    ctx.ui.notify("Vast is stopped. Starting the retained RTX 5090; your prompt is queued.", "info");
    timer = setInterval(() => renderWake(ctx), 1000);
  };

  const clearWakeDisplay = (ctx: ExtensionContext, outcome?: "ready" | "failed") => {
    if (timer === undefined) return;
    clearInterval(timer);
    timer = undefined;
    const elapsed = Math.max(0, Math.floor((Date.now() - wakeStartedAt) / 1000));
    ctx.ui.setWidget(WIDGET_KEY, undefined);
    ctx.ui.setWorkingMessage();
    if (outcome === "ready") {
      ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("success", `✓ Qwen ready after ${elapsed}s`));
      ctx.ui.notify(`Qwen is ready after ${elapsed}s. Sending your queued prompt.`, "info");
      readyTimer = setTimeout(() => {
        ctx.ui.setStatus(STATUS_KEY, undefined);
        readyTimer = undefined;
      }, 5000);
    } else if (outcome === "failed") {
      ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("error", "✗ Qwen startup failed"));
      ctx.ui.notify("Qwen startup failed. Pi will show the provider error.", "error");
    } else {
      ctx.ui.setStatus(STATUS_KEY, undefined);
    }
  };

  pi.on("before_provider_request", async (_event, ctx) => {
    if (!isQwenCloud(ctx) || timer !== undefined) return;
    try {
      const response = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(1500) });
      if (!response.ok) return;
      const health = await response.json() as { route?: unknown; wake_in_flight?: boolean };
      if (health.route == null || health.wake_in_flight === true) startWakeDisplay(ctx);
    } catch {
      // Do not alter or delay the provider request if the local status endpoint fails.
    }
  });

  pi.on("after_provider_response", (event, ctx) => {
    if (timer === undefined) return;
    clearWakeDisplay(ctx, event.status >= 200 && event.status < 300 ? "ready" : "failed");
  });

  pi.on("agent_end", (_event, ctx) => clearWakeDisplay(ctx));
  pi.on("session_shutdown", (_event, ctx) => {
    clearWakeDisplay(ctx);
    if (readyTimer !== undefined) clearTimeout(readyTimer);
    readyTimer = undefined;
    ctx.ui.setStatus(STATUS_KEY, undefined);
  });

  pi.registerCommand("qwen-wake-status", {
    description: "Show the current Qwen cloud route and wake state",
    handler: async (_args, ctx) => {
      try {
        const response = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(1500) });
        const health = await response.json() as {
          route?: { provider?: string } | null;
          wake_in_flight?: boolean;
          active_requests?: number;
          idle_seconds?: number;
        };
        const state = health.wake_in_flight
          ? "starting Vast"
          : health.route
            ? `ready on ${health.route.provider ?? "cloud"}`
            : "stopped; the next prompt will start Vast";
        ctx.ui.notify(`Qwen: ${state}. Active requests: ${health.active_requests ?? 0}. Idle: ${health.idle_seconds ?? 0}s.`, "info");
      } catch (error) {
        ctx.ui.notify(`Qwen wake status is unavailable: ${error instanceof Error ? error.message : String(error)}`, "error");
      }
    },
  });
}
