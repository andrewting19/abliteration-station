#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


MODELS = Path(os.environ.get("PI_CODING_AGENT_DIR", "/root/.pi/agent")) / "models.json"


def main() -> None:
    if not MODELS.is_file():
        return
    value = json.loads(MODELS.read_text(encoding="utf-8"))
    providers = value.get("providers")
    if not isinstance(providers, dict) or providers.pop("abliteration-station", None) is None:
        return
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
