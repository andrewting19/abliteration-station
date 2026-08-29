from __future__ import annotations

from dataclasses import dataclass
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

