#!/usr/bin/env python3
"""Run the real controller import-and-restore path on an isolated GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from abliteration_station.controller import Controller
from abliteration_station.providers.base import Route


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--inference-key-file", required=True)
    parser.add_argument("--lifecycle-token-file", required=True)
    parser.add_argument("--cache-command", required=True)
    args = parser.parse_args()
    root = args.work_directory.resolve()
    state_file = root / "cache-state.json"
    config = {
        "inference_key_file": args.inference_key_file,
        "model": {
            "id": "qwen38-cloud",
            "context_size": 262144,
            "quant_prefix": "Q3_K",
        },
        "kv_cache": {
            "enabled": True,
            "slot_id": 0,
            "filename": "real-pi-160k.slot",
            "state_file": str(state_file),
            "artifact_directory": str(root / "cache"),
            "runtime_fingerprint": "qwen38-q3-262144-medium-v1",
            "restore_timeout_seconds": 900,
        },
        "providers": {
            "vast": {
                "adapter": "abliteration_station.providers.vast:VastProvider",
                "ensure_command": "/bin/false",
                "instance_file": str(root / "instance-id"),
                "lifecycle_token_file": args.lifecycle_token_file,
                "cache_command": args.cache_command,
                "upstream": args.upstream.rstrip("/"),
                "cache_transfer_timeout_seconds": 1800,
            }
        },
    }
    route = Route(
        "vast",
        args.upstream.rstrip("/"),
        {"instance_id": args.instance_id, "restore_gate": 1},
    )
    restored = Controller(config).restore_cache(route)
    if not restored:
        raise SystemExit("cache restore gate failed")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    print(json.dumps({
        "restored": True,
        "instance_id": args.instance_id,
        "archive": state["artifact"]["sha256"]["archive"],
        "runtime": state["runtime"]["fingerprint"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
