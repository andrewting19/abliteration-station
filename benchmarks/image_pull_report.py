#!/usr/bin/env python3
"""Summarize OCI image transfer evidence without exposing provider log text."""
import argparse
import json
import math
import re
from pathlib import Path


def report(manifest, log, inet_mbps=None):
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("A platform image manifest with layers is required")
    if inet_mbps is not None and (not math.isfinite(inet_mbps) or inet_mbps <= 0):
        raise ValueError("Network rate must be finite and positive")
    for layer in layers:
        if (not re.fullmatch(r"sha256:[0-9a-f]{64}", layer.get("digest", ""))
                or type(layer.get("size")) is not int or layer["size"] < 0):
            raise ValueError("Invalid image layer metadata")
    prefixes = set(re.findall(
        r"\b([0-9a-f]{12,64}): (?:Download complete|Pull complete|Already exists)\b", log))
    known = set()
    for prefix in prefixes:
        matches = [x["digest"] for x in layers if x["digest"][7:].startswith(prefix)]
        if len(matches) == 1:
            known.add(matches[0])
    missing = [x for x in layers if x["digest"] not in known]
    total = sum(x["size"] for x in layers)
    return {
        "compressed_image_bytes": total,
        "layers_reported_complete": len(known),
        "layers_without_completion_evidence": [
            {"digest_prefix": x["digest"][7:19], "compressed_bytes": x["size"]}
            for x in missing],
        "uncached_transfer_seconds_at_supplied_rate": (
            total * 8 / (inet_mbps * 1_000_000) if inet_mbps is not None else None),
        "caveat": "Unreported layers may be cached or partly downloaded. The rate is an estimate, not a guaranteed limit. Startup and prefill are excluded.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("provider_log", type=Path)
    parser.add_argument("--inet-mbps", type=float)
    args = parser.parse_args()
    print(json.dumps(report(json.loads(args.manifest.read_text()),
                            args.provider_log.read_text(), args.inet_mbps), indent=2))
