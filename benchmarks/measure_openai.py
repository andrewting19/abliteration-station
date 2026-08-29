#!/usr/bin/env python3
"""Measure one streaming OpenAI-compatible request without storing its prompt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def integer(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def quality_pass(text: str, rules: dict[str, Any]) -> bool:
    if len(text) < int(rules.get("minimum_output_chars", 0)):
        return False
    if any(item not in text for item in rules.get("required_substrings", [])):
        return False
    if any(item in text for item in rules.get("forbidden_substrings", [])):
        return False
    return True


def event_payload(line: bytes) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped.startswith(b"data:"):
        return None
    value = stripped[5:].strip()
    if value == b"[DONE]":
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None


def run(manifest: dict[str, Any], base_url: str, api_key: str) -> dict[str, Any]:
    request_body = dict(manifest["request"])
    request_body["stream"] = True
    request_body["stream_options"] = {"include_usage": True}
    body = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    started_wall = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    first_token_at: float | None = None
    output: list[str] = []
    usage: dict[str, Any] = {}
    timings: dict[str, Any] = {}
    error: str | None = None

    try:
        with urllib.request.urlopen(request, timeout=7200) as response:
            for line in response:
                event = event_payload(line)
                if event is None:
                    continue
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                if isinstance(event.get("timings"), dict):
                    timings = event["timings"]
                choices = event.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                piece = str(delta.get("reasoning_content") or "") + str(delta.get("content") or "")
                if piece:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                    output.append(piece)
    except Exception as caught:  # Result files record request failures for comparisons.
        error = f"{type(caught).__name__}: {caught}"

    finished = time.monotonic()
    total_seconds = finished - started
    prompt_tokens = integer(usage.get("prompt_tokens")) or integer(timings.get("prompt_n")) or 0
    completion_tokens = integer(usage.get("completion_tokens")) or integer(timings.get("predicted_n")) or 0
    decode_tps = number(timings.get("predicted_per_second"))
    prefill_tps = number(timings.get("prompt_per_second"))
    drafted = integer(timings.get("draft_n"))
    accepted = integer(timings.get("draft_n_accepted"))
    acceptance = accepted / drafted if drafted and accepted is not None else None
    hourly = float(manifest.get("hourly_compute_usd", 0.0))
    turn_cost = hourly * total_seconds / 3600
    output_cost = turn_cost * 1_000_000 / completion_tokens if completion_tokens else None
    text = "".join(output)
    passed = error is None and quality_pass(text, manifest.get("quality", {}))

    return {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "variant": manifest["variant"],
        "workload_class": manifest["workload_class"],
        "started_at": started_wall,
        "success": error is None,
        "quality_pass": passed,
        "error": error,
        "latency": {
            "lifecycle_seconds": None,
            "time_to_first_token_seconds": first_token_at - started if first_token_at else None,
            "total_seconds": total_seconds,
            "prefill_tokens_per_second": prefill_tps,
            "decode_tokens_per_second": decode_tps,
        },
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "drafted": drafted,
            "accepted": accepted,
            "acceptance_rate": acceptance,
        },
        "cost": {
            "hourly_compute_usd": hourly,
            "turn_compute_usd": turn_cost,
            "usd_per_million_output_tokens": output_cost,
        },
        "host": {"hostname": socket.gethostname(), "platform": platform.platform()},
        "runtime": {
            "git_revision": os.environ.get("ABLITERATION_STATION_REVISION"),
            "server_timings": timings,
        },
        "tags": manifest.get("tags", []),
        "output": {
            "characters": len(text),
            "sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = run(manifest, args.base_url, args.api_key_file.read_text(encoding="utf-8").strip())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["success"] and result["quality_pass"] else 1)


if __name__ == "__main__":
    main()
