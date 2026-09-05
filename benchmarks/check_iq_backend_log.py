#!/usr/bin/env python3
"""Reject empty or incomplete console output from the pinned backend test."""
import re
import sys
from pathlib import Path

TYPES = {"iq2_xxs", "iq2_xs", "iq2_s", "iq3_xxs", "iq3_s", "iq4_xs", "iq4_nl"}
BATCHES = {1, 4, 5, 6, 7, 8}


def check(text):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if "FAIL" in text:
        raise ValueError("Backend reported failure")
    seen = set()
    for line in text.splitlines():
        if not re.search(r"\):\s*OK\s*$", line):
            continue
        match = re.search(r"MUL_MAT\(type_a=(\w+),.*?\bn=(\d+),", line)
        if match:
            seen.add((match[1].lower(), int(match[2])))
    missing = {(kind, n) for kind in TYPES for n in BATCHES} - seen
    if missing:
        raise ValueError(f"Missing passed IQ/batch cases: {sorted(missing)}")
    return len(seen)


if __name__ == "__main__":
    print(f"Passed coverage: {check(Path(sys.argv[1]).read_text())} type/batch pairs")
