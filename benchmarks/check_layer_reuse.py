#!/usr/bin/env python3
"""Compare large model-layer reuse between two single-platform OCI images."""
import argparse
import json
import subprocess


def compare(left, right, minimum_bytes=1_000_000_000):
    if "layers" not in left or "layers" not in right:
        raise ValueError("Use single-platform image manifests, not image indexes")
    previous = {item["digest"] for item in left["layers"] if item["size"] >= minimum_bytes}
    current = [item for item in right["layers"] if item["size"] >= minimum_bytes]
    changed = [item for item in current if item["digest"] not in previous]
    return {
        "large_layer_count": len(current),
        "reused_large_layer_count": len(current) - len(changed),
        "changed_large_layer_bytes": sum(item["size"] for item in changed),
        "all_large_layers_reused": bool(current) and not changed,
        "minimum_layer_bytes": minimum_bytes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("previous")
    parser.add_argument("current")
    parser.add_argument("--require-reuse", action="store_true")
    args = parser.parse_args()
    manifests = [json.loads(subprocess.check_output([
        "docker", "buildx", "imagetools", "inspect", "--raw", ref], text=True))
        for ref in (args.previous, args.current)]
    result = compare(*manifests)
    print(json.dumps(result, sort_keys=True))
    if args.require_reuse and not result["all_large_layers_reused"]:
        raise SystemExit("Unchanged model layers were not reused")


if __name__ == "__main__":
    main()
