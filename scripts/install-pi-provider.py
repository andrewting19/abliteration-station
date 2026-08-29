#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODELS = Path(os.environ.get("PI_CODING_AGENT_DIR", "/root/.pi/agent")) / "models.json"


def main() -> None:
    value = json.loads(MODELS.read_text(encoding="utf-8")) if MODELS.is_file() else {}
    providers = value.setdefault("providers", {})
    providers["qwen-cloud"] = {
        "baseUrl": "http://127.0.0.1:17072/v1",
        "api": "openai-completions",
        "apiKey": "!/usr/local/lib/qwen-cloud/vast/inference-key",
        "authHeader": True,
        "models": [{
            "id": "qwen38-cloud",
            "name": "Qwen3.8 27B Unleashed Q3 + DFlash2",
            "reasoning": True,
            "thinkingLevelMap": {
                "minimal": "low", "low": "low", "medium": "medium",
                "high": "xhigh", "xhigh": "xhigh", "max": "xhigh",
            },
            "input": ["text"],
            "contextWindow": 262144,
            "maxTokens": 262144,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "compat": {
                "supportsFinishReason": False,
                "thinkingFormat": "chat-template",
                "chatTemplateKwargs": {
                    "enable_thinking": {"$var": "thinking.enabled"},
                    "preserve_thinking": True,
                    "reasoning_effort": {"$var": "thinking.effort", "omitWhenOff": True},
                },
            },
        }],
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    MODELS.parent.mkdir(parents=True, exist_ok=True)
    if MODELS.is_file():
        shutil.copy2(MODELS, MODELS.with_name(f"models.json.before-qwen-cloud-{stamp}.bak"))
    descriptor, temporary = tempfile.mkstemp(prefix="models.", suffix=".json", dir=MODELS.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, MODELS)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    main()
