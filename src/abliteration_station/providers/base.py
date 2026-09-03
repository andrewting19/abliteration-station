from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Route:
    provider: str
    upstream: str
    identity: dict[str, Any]


class Provider(Protocol):
    name: str

    def doctor(self) -> list[str]: ...

    def ensure(self) -> Route: ...

    def stop(self) -> None: ...

    def status(self) -> dict[str, Any]: ...

    def runtime_fingerprint(self, route: Route) -> dict[str, Any]: ...

    def export_cache(self, route: Route, filename: str, destination: Path) -> dict[str, Any]: ...

    def import_cache(
        self, route: Route, filename: str, source: Path, manifest: dict[str, Any]
    ) -> None: ...
