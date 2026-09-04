from __future__ import annotations

import json
import fcntl
import hashlib
import importlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import atomic_json, read_secret
from .errors import LifecycleError, ProviderUnavailable
from .providers.base import Provider, Route

BUILTIN_ADAPTERS = {
    "vast": "abliteration_station.providers.vast:VastProvider",
}


def make_provider(name: str, config: dict[str, Any]) -> Provider:
    provider_config = config.get("providers", {}).get(name, {})
    adapter = provider_config.get("adapter") or BUILTIN_ADAPTERS.get(name)
    if not adapter or not isinstance(adapter, str) or ":" not in adapter:
        raise ProviderUnavailable(f"provider {name} has no valid adapter")
    module_name, class_name = adapter.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        provider_class = getattr(module, class_name)
        provider = provider_class(provider_config)
    except (ImportError, AttributeError, TypeError) as error:
        raise ProviderUnavailable(f"provider {name} adapter {adapter} could not load: {error}") from error
    for method in ("doctor", "ensure", "stop", "status"):
        if not callable(getattr(provider, method, None)):
            raise ProviderUnavailable(f"provider {name} adapter is missing {method}()")
    return provider


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
        deadline = time.monotonic() + float(self.config.get("ensure_lock_timeout_seconds", 7200))
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

    def _cache_config(self) -> dict[str, Any] | None:
        cache = self.config.get("kv_cache", {})
        if not isinstance(cache, dict) or not cache.get("enabled", False):
            return None
        return cache

    def _cache_fingerprint(self) -> str:
        model = self.config.get("model", {})
        cache = self._cache_config() or {}
        identity = {
            "model_id": model.get("id"),
            "context_size": model.get("context_size"),
            "quant_prefix": model.get("quant_prefix"),
            "runtime_fingerprint": cache.get("runtime_fingerprint"),
            "slot_id": int(cache.get("slot_id", 0)),
            "filename": cache.get("filename", "pi-session.slot"),
        }
        value = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    def _cache_state_file(self) -> Path:
        cache = self._cache_config() or {}
        return Path(cache.get("state_file", "/var/lib/abliteration-station/kv-cache-state.json"))

    def _cache_artifact_directory(self) -> Path:
        cache = self._cache_config() or {}
        return Path(cache.get("artifact_directory", "/var/lib/abliteration-station/kv-cache"))

    def save_cache(self, route: Route) -> bool:
        cache = self._cache_config()
        if cache is None:
            return False
        slot_id = int(cache.get("slot_id", 0))
        filename = str(cache.get("filename", "pi-session.slot"))
        try:
            response = self._request_json(
                route.upstream,
                f"/slots/{slot_id}?action=save",
                body={"filename": filename},
                timeout=float(cache.get("save_timeout_seconds", 600)),
            )
            if response.get("error"):
                raise LifecycleError(f"slot save returned an error: {response['error']}")
            n_saved = response.get("n_saved")
            if not isinstance(n_saved, int) or n_saved <= 0:
                raise LifecycleError(
                    f"slot save returned an invalid token count: {n_saved!r}"
                )
            provider = make_provider(route.provider, self.config)
            runtime_method = getattr(provider, "runtime_fingerprint", None)
            if not callable(runtime_method):
                raise LifecycleError(f"provider {route.provider} cannot identify its live runtime")
            runtime = runtime_method(route)
            export_portable = bool(cache.get("portable_export_on_save", False))
            artifact = None
            if export_portable:
                export = getattr(provider, "export_cache", None)
                if not callable(export):
                    raise LifecycleError(f"provider {route.provider} cannot export a portable cache")
                artifact = export(route, filename, self._cache_artifact_directory())
            state = {
                "schema_version": 1,
                "fingerprint": self._cache_fingerprint(),
                "runtime": runtime,
                "provider": route.provider,
                "identity": route.identity,
                "filename": filename,
                "storage": "portable" if artifact is not None else "provider-local",
                "saved_unix_ms": int(time.time() * 1000),
                "server_response": {
                    key: response[key]
                    for key in ("filename", "n_saved", "n_written", "timings")
                    if key in response
                },
            }
            if artifact is not None:
                state["artifact"] = artifact
            atomic_json(
                self._cache_state_file(),
                state,
            )
            return True
        except (LifecycleError, OSError, TypeError, ValueError) as error:
            print(f"KV cache save was not available; continuing with a cold fallback: {error}", file=sys.stderr)
            return False

    def restore_cache(self, route: Route) -> bool:
        cache = self._cache_config()
        if cache is None:
            return False
        try:
            state = json.loads(self._cache_state_file().read_text(encoding="utf-8"))
            if state.get("fingerprint") != self._cache_fingerprint():
                raise LifecycleError("checkpoint fingerprint does not match this model runtime")
            provider = make_provider(route.provider, self.config)
            runtime_method = getattr(provider, "runtime_fingerprint", None)
            if not callable(runtime_method):
                raise LifecycleError(f"provider {route.provider} cannot identify its live runtime")
            saved_runtime = state.get("runtime")
            live_runtime = runtime_method(route)
            if not isinstance(saved_runtime, dict) or saved_runtime.get("fingerprint") != live_runtime.get("fingerprint"):
                raise LifecycleError("checkpoint live-runtime fingerprint does not match this host")
            if state.get("identity") != route.identity:
                import_cache = getattr(provider, "import_cache", None)
                if not callable(import_cache):
                    raise LifecycleError(f"provider {route.provider} cannot import a portable cache")
                artifact = state.get("artifact")
                if not isinstance(artifact, dict):
                    raise LifecycleError("portable cache metadata is missing")
                import_cache(route, str(state["filename"]), self._cache_artifact_directory(), artifact)
            slot_id = int(cache.get("slot_id", 0))
            response = self._request_json(
                route.upstream,
                f"/slots/{slot_id}?action=restore",
                body={"filename": str(state["filename"])},
                timeout=float(cache.get("restore_timeout_seconds", 600)),
            )
            if response.get("error"):
                raise LifecycleError(f"slot restore returned an error: {response['error']}")
            return True
        except (LifecycleError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"KV cache restore was not available; using a cold prefill: {error}", file=sys.stderr)
            return False

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
                cache = self._cache_config()
                if cache is not None and cache.get("restore_on_wake", True):
                    self.restore_cache(route)
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
        active = self._active_route()
        if provider_name is None and active is not None:
            provider_name = active.provider
        if not provider_name:
            raise LifecycleError("no active provider is recorded")
        if active is not None and active.provider == provider_name:
            saved = self.save_cache(active)
            cache = self._cache_config()
            if cache is not None and cache.get("required_before_stop", True) and not saved:
                raise LifecycleError("provider stop was cancelled because the required KV cache save failed")
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
