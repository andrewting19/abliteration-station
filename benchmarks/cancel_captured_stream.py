#!/usr/bin/env python3
"""Cancel a captured request after its first token on an isolated model route."""
import argparse
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-file", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.capture.read_text())
    payload.update(stream=True, max_completion_tokens=4096, seed=424242)
    headers = {"Authorization": "Bearer " + args.api_key_file.read_text().strip(), "Content-Type": "application/json"}
    request = urllib.request.Request(args.base_url + "/v1/chat/completions", json.dumps(payload).encode(), headers)
    started = time.monotonic()
    first = None
    with urllib.request.urlopen(request, timeout=180) as response:
        for line in response:
            if not line.startswith(b"data:") or line[5:].strip() == b"[DONE]":
                continue
            event = json.loads(line[5:])
            if any(any((choice.get("delta") or {}).get(key) for key in ("content", "reasoning_content", "tool_calls")) for choice in event.get("choices", [])):
                first = time.monotonic() - started
                break
    if first is None:
        raise RuntimeError("No actual token arrived before cancellation")
    cancelled = time.monotonic()
    while time.monotonic() - cancelled < 5:
        with urllib.request.urlopen(urllib.request.Request(args.base_url + "/slots", headers=headers), timeout=2) as response:
            slots = json.load(response)
        if all(not slot.get("is_processing") for slot in slots):
            print(json.dumps({"first_token_seconds": first, "cancellation_to_idle_seconds": time.monotonic() - cancelled, "server_idle_after_cancel": True}))
            return
        time.sleep(0.1)
    raise RuntimeError("Server did not become idle after cancellation")


if __name__ == "__main__":
    main()
