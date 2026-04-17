from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    provider: str
    items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseToolAdapter(ABC):
    provider_name: str

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> ToolResult:
        """Execute provider search and return normalized result."""


def safe_limit(limit: int, *, default: int = 5, minimum: int = 1, maximum: int = 25) -> int:
    if limit < minimum:
        return default
    return min(limit, maximum)
