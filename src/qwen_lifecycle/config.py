from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("/etc/qwen-cloud/config.json")


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    selected = Path(path or os.environ.get("QWEN_CLOUD_CONFIG", DEFAULT_CONFIG))
    with selected.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["_config_path"] = str(selected)
    return config


def read_secret(path: str | os.PathLike[str]) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"secret file is empty: {path}")
    return value


def atomic_json(path: str | os.PathLike[str], value: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(destination)

