#!/usr/bin/env python3
"""Recover a historical request prefix by an exact tool-call ID match.

Private inputs and outputs must remain outside the repository. A later replay
must match expected_prompt_tokens before its performance result is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def reconstruct(payload, event):
    message = event.get("message") or {}
    if message.get("role") != "assistant" or message.get("stopReason") != "toolUse":
        raise ValueError("reference must be a completed assistant tool-use message")
    ids = {item["id"] for item in message.get("content", []) if item.get("type") == "toolCall"}
    if not ids:
        raise ValueError("reference has no tool-call IDs")
    matches = [index for index, item in enumerate(payload["messages"])
               if item.get("role") == "assistant" and
               ids.intersection(call.get("id") for call in item.get("tool_calls", []))]
    if len(matches) != 1:
        raise ValueError("tool-call ID did not identify one exact request boundary")
    result = dict(payload)
    result["messages"] = payload["messages"][:matches[0]]
    usage = message.get("usage") or {}
    metadata = {
        "reference_timestamp": event["timestamp"],
        "expected_prompt_tokens": usage.get("input", 0) + usage.get("cacheRead", 0) + usage.get("cacheWrite", 0),
        "reference_output_tokens": usage.get("output"),
        "message_count": matches[0],
        "requires_token_count_verification": True,
    }
    return result, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("session", type=Path)
    parser.add_argument("assistant_timestamp")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # NDJSON uses LF, not all Unicode separators accepted by splitlines().
    # Ignore unrelated tail records that may still be appended by live Pi.
    events = [json.loads(line) for line in args.session.read_text().split("\n")
              if args.assistant_timestamp in line]
    matching = [event for event in events if event.get("timestamp") == args.assistant_timestamp]
    if len(matching) != 1:
        raise ValueError("timestamp did not identify one exact session event")
    payload, metadata = reconstruct(json.loads(args.capture.read_text()), matching[0])
    data = json.dumps(payload).encode()
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    metadata["payload_sha256"] = hashlib.sha256(data).hexdigest()
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
