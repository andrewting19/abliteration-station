#!/usr/bin/env node

import fs from "node:fs";
import http from "node:http";
import path from "node:path";

const output = process.argv[2];
const port = Number(process.argv[3] ?? 18080);
if (!output || !Number.isInteger(port) || port < 1024 || port > 65535) {
  console.error("Usage: capture_openai_request.mjs PRIVATE_OUTPUT [PORT]");
  process.exit(2);
}

fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true, mode: 0o700 });

const server = http.createServer((request, response) => {
  const chunks = [];
  request.on("data", (chunk) => chunks.push(chunk));
  request.on("end", () => {
    const body = Buffer.concat(chunks);
    if (request.method !== "POST" || !request.url?.endsWith("/chat/completions")) {
      response.writeHead(404, { "content-type": "application/json" });
      response.end('{"error":"capture endpoint only accepts chat completions"}');
      return;
    }
    fs.writeFileSync(output, body, { mode: 0o600 });
    const id = "capture-only";
    const chunk = (delta, finish_reason = null) => JSON.stringify({
      id,
      object: "chat.completion.chunk",
      created: Math.floor(Date.now() / 1000),
      model: "qwen38-cloud",
      choices: [{ index: 0, delta, finish_reason }],
    });
    response.writeHead(200, {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      connection: "close",
    });
    response.write(`data: ${chunk({ role: "assistant", content: "" })}\n\n`);
    response.write(`data: ${chunk({ content: "CAPTURE_OK" })}\n\n`);
    response.write(`data: ${chunk({}, "stop")}\n\n`);
    response.end("data: [DONE]\n\n");
    setImmediate(() => server.close());
  });
});

server.listen(port, "127.0.0.1", () => {
  console.log(JSON.stringify({ status: "ready", port, output: path.resolve(output) }));
});
