#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODELS = Path(os.environ.get("PI_CODING_AGENT_DIR", "/root/.pi/agent")) / "models.json"
CONFIG = Path(os.environ.get("ABLITERATION_STATION_CONFIG", "/etc/abliteration-station/config.json"))


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    model = config["model"]
    model_id = model["id"]
    context_size = int(model["context_size"])
    value = json.loads(MODELS.read_text(encoding="utf-8")) if MODELS.is_file() else {}
    providers = value.setdefault("providers", {})
    providers["abliteration-station"] = {
        "baseUrl": "http://127.0.0.1:17072/v1",
        "api": "openai-completions",
        "apiKey": "!/usr/local/lib/abliteration-station/vast/inference-key",
        "authHeader": True,
        "models": [{
            "id": model_id,
            "name": model.get("display_name", model_id),
            "reasoning": True,
            "thinkingLevelMap": {
                "minimal": "low", "low": "low", "medium": "medium",
                "high": "xhigh", "xhigh": "xhigh", "max": "xhigh",
            },
            "input": ["text"],
            "contextWindow": context_size,
            "maxTokens": context_size,
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
        shutil.copy2(MODELS, MODELS.with_name(f"models.json.before-abliteration-station-{stamp}.bak"))
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
