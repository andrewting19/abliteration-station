#!/usr/bin/env python3
"""Summarize Abliteration Station JSONL results and show Pareto candidates."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def weighted_decode(records: list[dict[str, Any]]) -> float | None:
    tokens = 0
    seconds = 0.0
    for record in records:
        count = int(record["tokens"].get("completion") or 0)
        rate = record["latency"].get("decode_tokens_per_second")
        if count > 0 and isinstance(rate, (int, float)) and rate > 0:
            tokens += count
            seconds += count / rate
    return tokens / seconds if seconds else None


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["variant"], record["workload_class"])].append(record)
    summaries = []
    for (variant, workload), items in sorted(grouped.items()):
        total = [float(item["latency"]["total_seconds"]) for item in items if item["success"]]
        ttft = [float(value) for item in items if isinstance((value := item["latency"].get("time_to_first_token_seconds")), (int, float))]
        costs = [float(item["cost"]["turn_compute_usd"]) for item in items if item["success"]]
        summaries.append({
            "variant": variant,
            "workload_class": workload,
            "runs": len(items),
            "success_rate": sum(bool(item["success"]) for item in items) / len(items),
            "quality_rate": sum(bool(item["quality_pass"]) for item in items) / len(items),
            "total_seconds_p10": percentile(total, 0.10),
            "total_seconds_median": percentile(total, 0.50),
            "total_seconds_p90": percentile(total, 0.90),
            "ttft_seconds_median": percentile(ttft, 0.50),
            "decode_tps_token_weighted": weighted_decode(items),
            "turn_cost_usd_median": percentile(costs, 0.50),
        })
    return summaries


def pareto(summaries: list[dict[str, Any]]) -> list[str]:
    eligible = [item for item in summaries if item["quality_rate"] == 1.0 and item["success_rate"] == 1.0]
    winners = []
    for candidate in eligible:
        dominated = False
        for other in eligible:
            if other is candidate or other["workload_class"] != candidate["workload_class"]:
                continue
            c_speed = candidate["decode_tps_token_weighted"] or 0
            o_speed = other["decode_tps_token_weighted"] or 0
            c_cost = candidate["turn_cost_usd_median"] or float("inf")
            o_cost = other["turn_cost_usd_median"] or float("inf")
            if o_speed >= c_speed and o_cost <= c_cost and (o_speed > c_speed or o_cost < c_cost):
                dominated = True
                break
        if not dominated:
            winners.append(f"{candidate['variant']}:{candidate['workload_class']}")
    return winners


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    records = []
    for path in args.results:
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    summaries = summarize(records)
    print(json.dumps({"summaries": summaries, "quality_preserving_pareto": pareto(summaries)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
