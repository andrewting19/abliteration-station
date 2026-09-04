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
    validates_model_on_ensure = True

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

    def _cache_command(self) -> str:
        command = self.config.get("cache_command")
        if not command or not Path(command).is_file():
            raise LifecycleError(f"Vast cache command is missing: {command}")
        return str(command)

    @staticmethod
    def _instance_id(route: Route) -> str:
        value = str(route.identity.get("instance_id", ""))
        if not value.isdigit():
            raise LifecycleError("Vast route does not contain a valid instance ID")
        return value

    def _run_cache_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._cache_command(), *arguments],
            text=True,
            capture_output=True,
            timeout=float(self.config.get("cache_transfer_timeout_seconds", 1800)),
        )

    def runtime_fingerprint(self, route: Route) -> dict[str, Any]:
        result = self._run_cache_command("runtime-fingerprint", self._instance_id(route))
        if result.returncode:
            raise LifecycleError(f"Vast runtime fingerprint failed: {result.stderr.strip()}")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise LifecycleError("Vast runtime fingerprint returned invalid JSON") from error
        if not isinstance(value, dict) or not isinstance(value.get("fingerprint"), str):
            raise LifecycleError("Vast runtime fingerprint returned invalid metadata")
        return value

    def export_cache(self, route: Route, filename: str, destination: Path) -> dict[str, Any]:
        arguments = ["cache-export", self._instance_id(route), filename, str(destination)]
        replace_mode = str(self.config.get("cache_replace_mode", "atomic"))
        if replace_mode not in ("atomic", "in-place-safe"):
            raise LifecycleError(f"Vast cache replace mode is invalid: {replace_mode}")
        arguments.append(replace_mode)
        result = self._run_cache_command(*arguments)
        if result.returncode:
            raise LifecycleError(f"Vast cache export failed: {result.stderr.strip()}")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise LifecycleError("Vast cache export returned invalid JSON") from error
        if not isinstance(value, dict):
            raise LifecycleError("Vast cache export returned invalid metadata")
        return value

    def import_cache(
        self, route: Route, filename: str, source: Path, manifest: dict[str, Any]
    ) -> None:
        hashes = manifest.get("sha256", {})
        if not isinstance(hashes, dict) or not all(
            hashes.get(key) for key in ("slot", "checkpoint", "archive")
        ):
            raise LifecycleError("portable cache metadata does not contain all required hashes")
        result = self._run_cache_command(
            "cache-import", self._instance_id(route), filename, str(source),
            str(hashes["slot"]), str(hashes["checkpoint"]), str(hashes["archive"]),
        )
        if result.returncode:
            raise LifecycleError(f"Vast cache import failed: {result.stderr.strip()}")
