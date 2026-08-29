from __future__ import annotations

import json
import fcntl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import atomic_json, read_secret
from .errors import LifecycleError, ProviderUnavailable
from .providers.base import Provider, Route
from .providers.vast import VastProvider


def make_provider(name: str, config: dict[str, Any]) -> Provider:
    provider_config = config.get("providers", {}).get(name, {})
    if name == "vast":
        return VastProvider(provider_config)
    raise ProviderUnavailable(f"unknown provider: {name}")


class Controller:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.route_file = Path(config.get("route_file", "/run/abliteration-station/route.json"))

    def _active_route(self) -> Route | None:
        if not self.route_file.is_file():
            return None
        try:
            value = json.loads(self.route_file.read_text(encoding="utf-8"))
            provider = str(value["provider"])
            upstream = str(value["upstream"])
            identity = value.get("identity", {})
            if not isinstance(identity, dict):
                return None
            return Route(provider, upstream, identity)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _lock(self):
        lock_file = Path(self.config.get("ensure_lock_file", "/run/lock/abliteration-station-ensure.lock"))
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_file.open("a+", encoding="utf-8")
        deadline = time.monotonic() + float(self.config.get("ensure_lock_timeout_seconds", 1800))
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise LifecycleError("another provider start did not finish before the lock timeout")
                time.sleep(0.25)

    def _inference_key(self) -> str:
        return read_secret(self.config["inference_key_file"])

    def _request_json(
        self,
        url: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._inference_key()}",
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url.rstrip("/") + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise LifecycleError(f"model request failed at {url}: {error}") from error
        if not isinstance(result, dict):
            raise LifecycleError("model endpoint returned invalid JSON")
        return result

    def model_gate(self, upstream: str) -> None:
        response = self._request_json(upstream, "/v1/models", timeout=10)
        expected_model = self.config["model"]["id"]
        expected_context = int(self.config["model"]["context_size"])
        expected_quant_prefix = self.config["model"].get("quant_prefix", "")
        for model in response.get("data", []):
            meta = model.get("meta", {}) if isinstance(model, dict) else {}
            if (
                model.get("id") == expected_model
                and int(meta.get("n_ctx", 0)) == expected_context
                and str(meta.get("ftype", "")).startswith(expected_quant_prefix)
            ):
                return
        raise LifecycleError(
            f"endpoint did not report {expected_model}, context {expected_context}, quant {expected_quant_prefix}"
        )

    def chat_gate(self, upstream: str) -> None:
        effort = self.config["model"].get("reasoning_effort", "medium")
        response = self._request_json(
            upstream,
            "/v1/chat/completions",
            body={
                "model": self.config["model"]["id"],
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 64,
                "temperature": float(self.config["model"].get("temperature", 1.0)),
                "stream": False,
                "chat_template_kwargs": {
                    "enable_thinking": True,
                    "reasoning_effort": effort,
                },
            },
            timeout=float(self.config.get("chat_gate_timeout_seconds", 180)),
        )
        choices = response.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        if not (str(message.get("content", "")) + str(message.get("reasoning_content", ""))).strip():
            raise LifecycleError("model chat gate returned no content")

    def _ensure_locked(self) -> Route:
        active = self._active_route()
        if active:
            try:
                self.model_gate(active.upstream)
                self.chat_gate(active.upstream)
                return active
            except LifecycleError:
                pass

        failures: list[str] = []
        for name in self.config.get("provider_order", []):
            provider = make_provider(name, self.config)
            try:
                route = provider.ensure()
                self.model_gate(route.upstream)
                self.chat_gate(route.upstream)
                atomic_json(
                    self.route_file,
                    {
                        "provider": route.provider,
                        "upstream": route.upstream,
                        "identity": route.identity,
                        "ready_unix_ms": int(time.time() * 1000),
                    },
                )
                return route
            except ProviderUnavailable as error:
                failures.append(f"{name}: unavailable: {error}")
            except LifecycleError as error:
                failures.append(f"{name}: failed: {error}")
                try:
                    provider.stop()
                except Exception as cleanup_error:
                    failures.append(f"{name}: cleanup failed: {cleanup_error}")
                if not self.config.get("fallback_on_runtime_failure", True):
                    break
        raise LifecycleError("no provider passed the model gates; " + " | ".join(failures))

    def ensure(self) -> Route:
        lock_handle = self._lock()
        try:
            return self._ensure_locked()
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()

    def stop(self, provider_name: str | None = None) -> None:
        if provider_name is None and self.route_file.is_file():
            route = json.loads(self.route_file.read_text(encoding="utf-8"))
            provider_name = route.get("provider")
        if not provider_name:
            raise LifecycleError("no active provider is recorded")
        make_provider(provider_name, self.config).stop()
        self.route_file.unlink(missing_ok=True)

    def doctor(self) -> dict[str, list[str]]:
        return {
            name: make_provider(name, self.config).doctor()
            for name in self.config.get("provider_order", [])
        }

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "route": json.loads(self.route_file.read_text(encoding="utf-8"))
            if self.route_file.is_file()
            else None,
            "providers": {},
        }
        for name in self.config.get("provider_order", []):
            provider = make_provider(name, self.config)
            try:
                result["providers"][name] = provider.status()
            except Exception as error:
                result["providers"][name] = {"provider": name, "error": str(error)}
        return result
