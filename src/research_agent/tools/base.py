from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from aiolimiter import AsyncLimiter
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff, retry_with_backoff_sync  # noqa: F401 — re-exported for adapter consumption


@dataclass
class ToolResult:
    provider: str
    items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseToolAdapter(ABC):
    provider_name: str
    is_searcher: bool = True

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> ToolResult:
        """Execute provider search and return normalized result."""

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        """Async version of search. Defaults to running search in a thread."""
        import asyncio
        return await asyncio.to_thread(self.search, query, limit=limit)


class RateLimiter:
    """Dual-mode rate limiter supporting both sync and async call paths.

    Provides a shared rate limit that works for:
    - Sync calls via ``sync_acquire()`` (uses ``threading.Lock`` + ``time.sleep``)
    - Async calls via ``async_acquire()`` (uses ``aiolimiter.AsyncLimiter``)

    This means both ``search()`` (sync) and ``asearch()`` (async) are rate limited
    without blocking the async event loop.
    """

    def __init__(self, max_rate: float, time_period: float = 1.0) -> None:
        if max_rate <= 0:
            raise ValueError("max_rate must be > 0")
        self._async_limiter = AsyncLimiter(max_rate, time_period)
        self._sync_lock = threading.Lock()
        self._sync_interval = time_period / max_rate
        self._sync_last = 0.0

    def sync_acquire(self) -> None:
        """Blocking acquire for synchronous call paths."""
        with self._sync_lock:
            now = time.monotonic()
            elapsed = now - self._sync_last
            if elapsed < self._sync_interval:
                time.sleep(self._sync_interval - elapsed)
            self._sync_last = time.monotonic()

    async def async_acquire(self) -> None:
        """Non-blocking acquire for async call paths (awaits the token bucket)."""
        await self._async_limiter.acquire()


def safe_limit(limit: int, *, default: int = 5, minimum: int = 1, maximum: int = 25) -> int:
    if limit < minimum:
        return default
    return min(limit, maximum)
