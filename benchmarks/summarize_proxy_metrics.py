#!/usr/bin/env python3
"""Summarize privacy-safe metrics captured from real Pi requests."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def timing(record: dict[str, Any], key: str) -> float | None:
    value = (record.get("timings") or {}).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def weighted_rate(records: list[dict[str, Any]], token_key: str, rate_key: str) -> float | None:
    tokens = 0.0
    seconds = 0.0
    for record in records:
        count = timing(record, token_key)
        rate = timing(record, rate_key)
        if count and rate and rate > 0:
            tokens += count
            seconds += count / rate
    return tokens / seconds if seconds else None


def summarize(records: list[dict[str, Any]], hourly_rate: float) -> dict[str, Any]:
    totals = [float(item["total_seconds"]) for item in records if isinstance(item.get("total_seconds"), (int, float))]
    ttft = [float(item["first_response_byte_seconds"]) for item in records if isinstance(item.get("first_response_byte_seconds"), (int, float))]
    wakes = [float(item["wake_seconds"]) for item in records if isinstance(item.get("wake_seconds"), (int, float))]
    completion_tokens = sum(int((item.get("usage") or {}).get("completion_tokens") or 0) for item in records)
    drafted_tokens = sum(int((item.get("timings") or {}).get("draft_n") or 0) for item in records)
    accepted_tokens = sum(int((item.get("timings") or {}).get("draft_n_accepted") or 0) for item in records)
    measured_seconds = sum(totals)
    return {
        "requests": len(records),
        "successful_requests": sum(item.get("status") == 200 and not item.get("error") for item in records),
        "cancelled_requests": sum(bool(item.get("cancelled")) for item in records),
        "wake_requests": sum(bool(item.get("wake_required")) for item in records),
        "total_seconds_median": percentile(totals, 0.5),
        "total_seconds_p90": percentile(totals, 0.9),
        "first_response_byte_seconds_median": percentile(ttft, 0.5),
        "wake_seconds_median": percentile(wakes, 0.5),
        "prompt_tps_token_weighted": weighted_rate(records, "prompt_n", "prompt_per_second"),
        "decode_tps_token_weighted": weighted_rate(records, "predicted_n", "predicted_per_second"),
        "completion_tokens": completion_tokens,
        "drafted_tokens": drafted_tokens,
        "accepted_tokens": accepted_tokens,
        "draft_acceptance_rate": accepted_tokens / drafted_tokens if drafted_tokens else None,
        "measured_request_compute_usd": measured_seconds * hourly_rate / 3600,
        "usd_per_million_output_tokens": (
            measured_seconds * hourly_rate / 3600 * 1_000_000 / completion_tokens
            if completion_tokens else None
        ),
        "note": "Compute estimate includes measured request time only. Add idle, storage, setup, and failed-rental cost separately.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--hourly-rate", type=float, required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.metrics.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps(summarize(records, args.hourly_rate), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
