#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function fail(message) {
  console.error(message);
  process.exit(2);
}

const values = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  values.set(process.argv[index], process.argv[index + 1]);
}
const sessionPath = values.get("--session");
const outputPath = values.get("--output");
const modulePath = values.get("--pi-module");
const systemPromptPath = values.get("--system-prompt");
if (!sessionPath || !outputPath || !modulePath) {
  fail("Usage: capture_pi_session.mjs --session FILE --output PRIVATE_FILE --pi-module INDEX_JS [--system-prompt FILE]");
}

const pi = await import(pathToFileURL(path.resolve(modulePath)).href);
if (typeof pi.parseSessionEntries !== "function" || typeof pi.buildSessionContext !== "function") {
  fail("The selected Pi module does not export the session conversion functions.");
}

const entries = pi.parseSessionEntries(fs.readFileSync(sessionPath, "utf8"));
const context = pi.buildSessionContext(entries);

function textContent(content) {
  if (typeof content === "string") return content;
  return (content ?? []).filter((part) => part.type === "text").map((part) => part.text).join("\n");
}

function convert(message) {
  if (message.role === "user") return { role: "user", content: textContent(message.content) };
  if (message.role === "assistant") {
    const result = {
      role: "assistant",
      content: (message.content ?? []).filter((part) => part.type === "text").map((part) => part.text).join("\n"),
    };
    const reasoning = (message.content ?? []).filter((part) => part.type === "thinking").map((part) => part.thinking).join("\n");
    if (reasoning) result.reasoning_content = reasoning;
    const calls = (message.content ?? []).filter((part) => part.type === "toolCall");
    if (calls.length) {
      result.tool_calls = calls.map((call) => ({
        id: call.id,
        type: "function",
        function: { name: call.name, arguments: JSON.stringify(call.arguments ?? {}) },
      }));
    }
    return result;
  }
  if (message.role === "toolResult") {
    return { role: "tool", tool_call_id: message.toolCallId, content: textContent(message.content) };
  }
  return { role: "user", content: textContent(message.content ?? message.summary ?? "") };
}

const sourceMessages = typeof pi.convertToLlm === "function" ? pi.convertToLlm(context.messages) : context.messages;
const messages = sourceMessages.map(convert).filter((message) => message.content || message.tool_calls);
if (systemPromptPath) {
  messages.unshift({ role: "system", content: fs.readFileSync(systemPromptPath, "utf8") });
}
const payload = {
  model: "qwen38-cloud",
  messages,
  max_tokens: 2048,
  temperature: 1,
  top_p: 0.95,
  top_k: 20,
  min_p: 0,
  repeat_penalty: 1,
  seed: 424242,
  stream: false,
  chat_template_kwargs: { enable_thinking: true, reasoning_effort: "medium" },
};
fs.mkdirSync(path.dirname(path.resolve(outputPath)), { recursive: true, mode: 0o700 });
fs.writeFileSync(outputPath, `${JSON.stringify(payload)}\n`, { mode: 0o600 });
console.log(JSON.stringify({ entries: entries.length, messages: messages.length, output: path.resolve(outputPath) }));
