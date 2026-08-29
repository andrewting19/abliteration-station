from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .errors import LifecycleError


class JsonClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = self.token
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:1000]
            raise LifecycleError(f"{method} {path} returned HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise LifecycleError(f"{method} {path} failed: {error.reason}") from error
        try:
            result = json.loads(payload)
        except json.JSONDecodeError as error:
            raise LifecycleError(f"{method} {path} did not return JSON") from error
        if not isinstance(result, dict):
            raise LifecycleError(f"{method} {path} returned an invalid JSON object")
        return result

