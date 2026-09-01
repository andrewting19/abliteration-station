import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const STATUS_KEY = "abliteration-station-wake";
const WIDGET_KEY = "abliteration-station-wake";
const HEALTH_URL = process.env.ABLITERATION_STATION_HEALTH_URL ?? "http://127.0.0.1:17072/healthz";
const CONFIG_FILE = process.env.ABLITERATION_STATION_CONFIG ?? "/etc/abliteration-station/config.json";
const CLI = process.env.ABLITERATION_STATION_CLI ?? "/usr/local/bin/abliteration-station";
const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type ModelConfig = {
  id: string;
  display_name?: string;
  context_size: number;
};

type Health = {
  route?: { provider?: string } | null;
  wake_in_flight?: boolean;
  active_requests?: number;
  idle_seconds?: number;
  idle_limit_seconds?: number;
  last_wake_error?: string | null;
  lifecycle?: {
    phase?: string;
    message?: string;
    phase_started_unix_ms?: number;
    eta_seconds?: number | null;
    instance_id?: number | null;
  } | null;
};

function readModelConfig(): ModelConfig {
  try {
    const config = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf8")) as { model?: Partial<ModelConfig> };
    if (config.model?.id && config.model.context_size) return config.model as ModelConfig;
  } catch {
    // The system service is optional during package installation.
  }
  return {
    id: "qwen38-cloud",
    display_name: "Qwen3.8-27B Unleashed Q3",
    context_size: 262144,
  };
}

async function readHealth(): Promise<Health> {
  const response = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(1500) });
  if (!response.ok) throw new Error(`local service returned HTTP ${response.status}`);
  return await response.json() as Health;
}

export default function (pi: ExtensionAPI) {
  const model = readModelConfig();
  let wakeStartedAt = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  let readyTimer: ReturnType<typeof setTimeout> | undefined;

  pi.registerProvider("abliteration-station", {
    name: "Abliteration Station",
    baseUrl: "http://127.0.0.1:17072/v1",
    apiKey: "!/usr/local/lib/abliteration-station/vast/inference-key",
    authHeader: true,
    api: "openai-completions",
    models: [{
      id: model.id,
      name: model.display_name ?? model.id,
      reasoning: true,
      thinkingLevelMap: {
        minimal: "low", low: "low", medium: "medium",
        high: "xhigh", xhigh: "xhigh", max: "xhigh",
      },
      input: ["text"],
      contextWindow: model.context_size,
      maxTokens: model.context_size,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      compat: {
        supportsFinishReason: false,
        thinkingFormat: "chat-template",
        chatTemplateKwargs: {
          enable_thinking: { $var: "thinking.enabled" },
          preserve_thinking: true,
          reasoning_effort: { $var: "thinking.effort", omitWhenOff: true },
        },
      },
    }],
  });

  const isStationModel = (ctx: ExtensionContext) =>
    ctx.model?.provider === "abliteration-station" || ctx.model?.id === model.id;

  const renderWake = async (ctx: ExtensionContext) => {
    const elapsed = Math.max(0, Math.floor((Date.now() - wakeStartedAt) / 1000));
    let message = `Starting Qwen... ${elapsed}s`;
    let detail = "Your prompt is queued and will send automatically.";
    try {
      const health = await readHealth();
      const lifecycle = health.lifecycle;
      if (lifecycle?.message) {
        const phaseElapsed = lifecycle.phase_started_unix_ms
          ? Math.max(0, Math.floor((Date.now() - lifecycle.phase_started_unix_ms) / 1000))
          : elapsed;
        const eta = lifecycle.eta_seconds;
        const remaining = typeof eta === "number" ? Math.max(0, eta - phaseElapsed) : null;
        message = `${lifecycle.message} — ${phaseElapsed}s`;
        detail = remaining === null
          ? "Provider completion time is unknown. Your prompt remains queued."
          : remaining === 0 && phaseElapsed > eta
            ? "The phase estimate was exceeded. The provider is still working and your prompt remains queued."
            : `Estimated time remaining for this phase: about ${remaining}s. Your prompt remains queued.`;
      }
    } catch {
      // Keep the local elapsed display if the status request fails.
    }
    ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("warning", `o ${message}`));
    ctx.ui.setWidget(
      WIDGET_KEY,
      [ctx.ui.theme.fg("warning", message), ctx.ui.theme.fg("dim", detail)],
      { placement: "belowEditor" },
    );
    ctx.ui.setWorkingMessage(message);
  };

  const startWakeDisplay = (ctx: ExtensionContext) => {
    if (timer !== undefined) return;
    if (readyTimer !== undefined) clearTimeout(readyTimer);
    readyTimer = undefined;
    wakeStartedAt = Date.now();
    void renderWake(ctx);
    ctx.ui.notify("The GPU is stopped. Abliteration Station is starting it now.", "info");
    timer = setInterval(() => void renderWake(ctx), 1000);
  };

  const clearWakeDisplay = (ctx: ExtensionContext, outcome?: "ready" | "failed") => {
    if (timer === undefined) return;
    clearInterval(timer);
    timer = undefined;
    const elapsed = Math.max(0, Math.floor((Date.now() - wakeStartedAt) / 1000));
    ctx.ui.setWidget(WIDGET_KEY, undefined);
    ctx.ui.setWorkingMessage();
    if (outcome === "ready") {
      ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("success", `Qwen ready after ${elapsed}s`));
      ctx.ui.notify(`Qwen is ready after ${elapsed}s. Pi is sending your prompt.`, "info");
      readyTimer = setTimeout(() => {
        ctx.ui.setStatus(STATUS_KEY, undefined);
        readyTimer = undefined;
      }, 5000);
    } else if (outcome === "failed") {
      ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("error", "Qwen startup failed"));
      ctx.ui.notify("Qwen startup failed. Run /abliteration-doctor for details.", "error");
    } else {
      ctx.ui.setStatus(STATUS_KEY, undefined);
    }
  };

  pi.on("before_provider_request", async (_event, ctx) => {
    if (!isStationModel(ctx) || timer !== undefined) return;
    try {
      const health = await readHealth();
      if (health.route == null || health.wake_in_flight === true) startWakeDisplay(ctx);
    } catch {
      // Do not delay the provider request. Pi will report the provider error.
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

  pi.registerCommand("abliteration-status", {
    description: "Show the GPU route, request count, and idle state",
    handler: async (_args, ctx) => {
      try {
        const health = await readHealth();
        const state = health.wake_in_flight
          ? "starting Vast"
          : health.route
            ? `ready on ${health.route.provider ?? "cloud"}`
            : "stopped; the next prompt will start Vast";
        ctx.ui.notify(
          `Qwen is ${state}. Active requests: ${health.active_requests ?? 0}. Idle: ${health.idle_seconds ?? 0}/${health.idle_limit_seconds ?? "?"}s.`,
          health.last_wake_error ? "warning" : "info",
        );
      } catch (error) {
        ctx.ui.notify(`The Abliteration Station service is not ready: ${error instanceof Error ? error.message : String(error)}`, "error");
      }
    },
  });

  pi.registerCommand("abliteration-use", {
    description: "Select the Abliteration Station model with medium thinking",
    handler: async (_args, ctx) => {
      const selected = ctx.modelRegistry.find("abliteration-station", model.id);
      if (!selected) {
        ctx.ui.notify("The Abliteration Station model is not registered. Run /reload and try again.", "error");
        return;
      }
      if (!await pi.setModel(selected)) {
        ctx.ui.notify("The inference key is not installed. Run /abliteration-setup.", "error");
        return;
      }
      pi.setThinkingLevel("medium");
      ctx.ui.notify(`${selected.name} is active with medium thinking.`, "info");
    },
  });

  pi.registerCommand("abliteration-wake", {
    description: "Start the retained GPU before the next prompt",
    handler: async (_args, ctx) => {
      startWakeDisplay(ctx);
      ctx.ui.notify("Starting the GPU. Pi will show each provider and model phase below the editor.", "info");
      const result = await pi.exec(CLI, ["ensure"], { timeout: 900000 });
      clearWakeDisplay(ctx, result.code === 0 ? "ready" : "failed");
      ctx.ui.notify(result.code === 0 ? "Qwen is ready." : `GPU start failed: ${result.stderr.trim()}`, result.code === 0 ? "info" : "error");
    },
  });

  pi.registerCommand("abliteration-stop", {
    description: "Stop paid GPU compute and keep its retained storage",
    handler: async (_args, ctx) => {
      const result = await pi.exec(CLI, ["stop"], { timeout: 120000 });
      ctx.ui.notify(result.code === 0 ? "Paid GPU compute is stopped." : `GPU stop failed: ${result.stderr.trim()}`, result.code === 0 ? "info" : "error");
    },
  });

  pi.registerCommand("abliteration-doctor", {
    description: "Check the local service and provider configuration",
    handler: async (_args, ctx) => {
      const result = await pi.exec(CLI, ["doctor"], { timeout: 30000 });
      const message = (result.code === 0 ? result.stdout : result.stderr).trim() || `Doctor exited with status ${result.code}`;
      ctx.ui.notify(message, result.code === 0 ? "info" : "error");
    },
  });

  pi.registerCommand("abliteration-setup", {
    description: "Install the durable local lifecycle service from this package",
    handler: async (_args, ctx) => {
      const installer = path.join(PACKAGE_ROOT, "scripts", "install.sh");
      if (!fs.existsSync(installer)) {
        ctx.ui.notify(`Installer not found at ${installer}. Reinstall the Pi package.`, "error");
        return;
      }
      const command = typeof process.getuid === "function" && process.getuid() === 0 ? installer : "sudo";
      const args = command === installer ? [PACKAGE_ROOT] : ["-n", installer, PACKAGE_ROOT];
      const result = await pi.exec(command, args, { timeout: 120000 });
      if (result.code === 0) {
        ctx.ui.notify("The service is installed. Run `sudo abliteration-station-configure` in a terminal to add private keys.", "info");
      } else {
        ctx.ui.notify(`Automatic setup needs passwordless sudo. Run: sudo ${installer} ${PACKAGE_ROOT}`, "warning");
      }
    },
  });
}
