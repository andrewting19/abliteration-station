#!/usr/bin/env python3
"""Apply safe Abliteration Station configuration migrations."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


OLD_BOOTSTRAP_TIMEOUT = 1800
NEW_BOOTSTRAP_TIMEOUT = 7200


def migrate(config: dict) -> bool:
    changed = False
    if config.get("ensure_lock_timeout_seconds") == OLD_BOOTSTRAP_TIMEOUT:
        config["ensure_lock_timeout_seconds"] = NEW_BOOTSTRAP_TIMEOUT
        changed = True

    vast = config.get("providers", {}).get("vast")
    if isinstance(vast, dict) and vast.get("start_timeout_seconds") == OLD_BOOTSTRAP_TIMEOUT:
        vast["start_timeout_seconds"] = NEW_BOOTSTRAP_TIMEOUT
        changed = True
    return changed


def main() -> int:
    path = Path(sys.argv[1])
    config = json.loads(path.read_text(encoding="utf-8"))
    if not migrate(config):
        return 0

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
