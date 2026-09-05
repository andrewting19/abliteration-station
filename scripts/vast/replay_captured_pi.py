#!/usr/bin/env python3
"""Replay one captured Pi request with fixed sampling for server A/B tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:17070")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        default=Path("/workspace/qwen38/api_key"),
    )
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--stream", action="store_true", help="Measure first actual token as well as server decode timing")
    parser.add_argument(
        "--minimum-cached-tokens",
        type=int,
        default=0,
        help="Fail after the safe request fallback if the server reused fewer prompt tokens.",
    )
    args = parser.parse_args()

    payload = json.loads(args.capture.read_text())
    payload["stream"] = args.stream
    payload.pop("stream_options", None)
    if args.stream:
        payload["stream_options"] = {"include_usage": True}
    payload["max_completion_tokens"] = args.max_tokens
    payload["seed"] = args.seed
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    api_key = args.api_key_file.read_text().strip()
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{args.base_url}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.monotonic()
    first_token_seconds = None
    with urllib.request.urlopen(request, timeout=7200) as response:
        if not args.stream:
            result = json.load(response)
        else:
            streamed_message = {"content": "", "reasoning_content": "", "tool_calls": []}
            calls = {}
            result = {"choices": [{"message": streamed_message, "finish_reason": None}]}
            for line in response:
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    break
                if not data:
                    continue
                event = json.loads(data)
                if event.get("error"):
                    raise RuntimeError("inference stream reported an error")
                for key in ("usage", "timings"):
                    if event.get(key):
                        result[key] = event[key]
                for choice in event.get("choices", []):
                    delta = choice.get("delta") or {}
                    if first_token_seconds is None and any(delta.get(key) for key in ("content", "reasoning_content", "reasoning", "tool_calls")):
                        first_token_seconds = time.monotonic() - started
                    streamed_message["content"] += delta.get("content") or ""
                    streamed_message["reasoning_content"] += delta.get("reasoning_content") or delta.get("reasoning") or ""
                    for call in delta.get("tool_calls") or []:
                        item = calls.setdefault(call.get("index", 0), {"function": {"name": "", "arguments": ""}})
                        for key in ("name", "arguments"):
                            item["function"][key] += (call.get("function") or {}).get(key) or ""
                    if choice.get("finish_reason") is not None:
                        result["choices"][0]["finish_reason"] = choice["finish_reason"]
            streamed_message["tool_calls"] = list(calls.values())
            if result["choices"][0]["finish_reason"] is None:
                raise RuntimeError("stream ended without finish_reason")
    elapsed = time.monotonic() - started
    message = result["choices"][0]["message"]
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""
    timings = result.get("timings") or {}
    prompt_details = (result.get("usage") or {}).get("prompt_tokens_details") or {}
    cached_tokens = max(
        int(timings.get("cache_n") or 0),
        int(prompt_details.get("cached_tokens") or 0),
    )
    print(
        json.dumps(
            {
                "elapsed_seconds": round(elapsed, 3),
                "first_token_seconds": first_token_seconds,
                "finish_reason": result["choices"][0].get("finish_reason"),
                "usage": result.get("usage"),
                "timings": timings,
                "cached_tokens": cached_tokens,
                "minimum_cached_tokens": args.minimum_cached_tokens,
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "reasoning_sha256": hashlib.sha256(reasoning.encode()).hexdigest(),
                "content_chars": len(content),
                "reasoning_chars": len(reasoning),
                "tool_calls": [
                    call.get("function", {}).get("name")
                    for call in message.get("tool_calls") or []
                ],
            },
            sort_keys=True,
        )
    )
    if cached_tokens < args.minimum_cached_tokens:
        raise SystemExit(
            f"cache prefix mismatch: reused {cached_tokens} tokens; "
            f"required at least {args.minimum_cached_tokens}. "
            "The server safely completed the request with a full prefill."
        )


if __name__ == "__main__":
    main()
