from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("/etc/abliteration-station/config.json")


def validate_config(config: dict[str, Any]) -> None:
    providers = config.get("providers")
    order = config.get("provider_order")
    model = config.get("model")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("providers must be a non-empty object")
    if not isinstance(order, list) or not order or not all(isinstance(name, str) for name in order):
        raise ValueError("provider_order must be a non-empty string list")
    missing = [name for name in order if name not in providers]
    if missing:
        raise ValueError(f"provider_order references missing providers: {', '.join(missing)}")
    if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"]:
        raise ValueError("model.id must be a non-empty string")
    if not isinstance(model.get("context_size"), int) or model["context_size"] <= 0:
        raise ValueError("model.context_size must be a positive integer")


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    selected = Path(path or os.environ.get("ABLITERATION_STATION_CONFIG", DEFAULT_CONFIG))
    with selected.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validate_config(config)
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
