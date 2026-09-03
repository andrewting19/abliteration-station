#!/usr/bin/env python3
"""Run the real controller cache-save and provider-stop path on an isolated GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from abliteration_station.config import atomic_json
from abliteration_station.controller import Controller


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--inference-key-file", required=True)
    parser.add_argument("--lifecycle-token-file", required=True)
    parser.add_argument("--cache-command", required=True)
    args = parser.parse_args()
    if not args.instance_id.isdigit():
        raise SystemExit("instance ID must be numeric")

    root = args.work_directory.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    route_file = root / "route.json"
    instance_file = root / "instance-id"
    state_file = root / "cache-state.json"
    artifact_directory = root / "cache"
    instance_file.write_text(f"{args.instance_id}\n", encoding="utf-8")
    instance_file.chmod(0o600)
    route = {
        "provider": "vast",
        "upstream": args.upstream.rstrip("/"),
        "identity": {"instance_id": args.instance_id},
    }
    atomic_json(route_file, route)
    config = {
        "route_file": str(route_file),
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
            "artifact_directory": str(artifact_directory),
            "runtime_fingerprint": "qwen38-q3-262144-medium-v1",
            "save_timeout_seconds": 900,
        },
        "providers": {
            "vast": {
                "adapter": "abliteration_station.providers.vast:VastProvider",
                "ensure_command": "/bin/false",
                "instance_file": str(instance_file),
                "lifecycle_token_file": args.lifecycle_token_file,
                "cache_command": args.cache_command,
                "upstream": args.upstream.rstrip("/"),
                "cache_transfer_timeout_seconds": 1800,
            }
        },
    }
    Controller(config).stop()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    print(json.dumps({
        "stopped": args.instance_id,
        "state_file": str(state_file),
        "artifact": state.get("artifact"),
        "runtime": state.get("runtime"),
        "server_response": state.get("server_response"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
