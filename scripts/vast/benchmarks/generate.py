#!/usr/bin/env python3
"""Generate secret-free long-context requests for fresh-host speed gates."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent / "captures"


def payload(lines: int, instruction: str) -> dict:
    source = "".join(
        f"def step_{index}(value):\n    return value + {index % 97}\n\n"
        for index in range(lines)
    )
    return {
        "model": "qwen38-cloud",
        "messages": [
            {
                "role": "developer",
                "content": "You are a coding agent. Analyze the supplied synthetic Python module.",
            },
            {
                "role": "user",
                "content": f"{source}\n{instruction}",
            },
        ],
        "temperature": 1.0,
        "stream": False,
        "chat_template_kwargs": {
            "enable_thinking": True,
            "reasoning_effort": "medium",
        },
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    requests = [
        payload(12_500, "Identify three repeated structural patterns."),
        payload(13_250, "Propose a concise refactor and explain its invariants."),
    ]
    for index, request in enumerate(requests, start=1):
        path = ROOT / f"{index:03d}-chat-completions.json"
        path.write_text(json.dumps(request, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
