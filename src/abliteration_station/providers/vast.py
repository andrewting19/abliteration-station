from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from ..config import read_secret
from ..errors import LifecycleError, ProviderUnavailable
from .base import Route


class VastProvider:
    """Adapter for the Vast.ai lifecycle scripts."""

    name = "vast"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def doctor(self) -> list[str]:
        errors = []
        command = self.config.get("ensure_command")
        if not command or not Path(command).is_file():
            errors.append(f"Vast ensure command is missing: {command}")
        for key in ("instance_file", "lifecycle_token_file", "upstream"):
            if not self.config.get(key):
                errors.append(f"vast.{key} is not configured")
        return errors

    def ensure(self) -> Route:
        problems = self.doctor()
        if problems:
            raise ProviderUnavailable("; ".join(problems))
        result = subprocess.run(
            [self.config["ensure_command"]],
            text=True,
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=float(self.config.get("start_timeout_seconds", 7200)),
        )
        if result.returncode:
            raise LifecycleError(
                f"Vast ensure command exited with status {result.returncode}; "
                "see the progress output above"
            )
        instance_id = Path(self.config["instance_file"]).read_text(encoding="utf-8").strip()
        return Route(self.name, self.config["upstream"].rstrip("/"), {"instance_id": instance_id})

    def stop(self) -> None:
        instance_file = Path(self.config["instance_file"])
        if not instance_file.is_file():
            return
        instance_id = instance_file.read_text(encoding="utf-8").strip()
        token = read_secret(self.config["lifecycle_token_file"])
        request = urllib.request.Request(
            f"https://console.vast.ai/api/v0/instances/{instance_id}",
            data=json.dumps({"state": "stopped"}).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        except Exception as error:
            raise LifecycleError(f"Vast stop failed for instance {instance_id}: {error}") from error

    def status(self) -> dict[str, Any]:
        instance_file = Path(self.config.get("instance_file", ""))
        return {
            "provider": self.name,
            "configured": not self.doctor(),
            "instance_id": instance_file.read_text(encoding="utf-8").strip()
            if instance_file.is_file()
            else None,
        }
