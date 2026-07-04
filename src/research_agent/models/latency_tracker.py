"""Latency tracking and latency-aware routing for multi-provider LLM calls.

Tracks response times per provider/model and provides routing decisions
so that interactive tasks use the fastest available provider while batch
tasks can use slower/cheaper providers.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

from research_agent.config import load_settings


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Latency tracking
# ---------------------------------------------------------------------------

@dataclass
class LatencySample:
    """A single latency measurement for a provider/model invocation."""
    provider: str
    model: str
    duration_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)


class LatencyTracker:
    """Tracks response-time statistics per provider.

    Maintains a sliding window of recent samples so routing decisions
    reflect current conditions, not stale history.
    """

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self._samples: dict[str, list[LatencySample]] = {}
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def record(
        self,
        provider: str,
        model: str,
        duration_ms: float,
        success: bool = True,
    ) -> None:
        """Record a single latency measurement (async-safe)."""
        sample = LatencySample(
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            success=success,
        )
        async with self._async_lock:
            self._samples.setdefault(provider, []).append(sample)
            # Trim to window size
            if len(self._samples[provider]) > self.window_size:
                self._samples[provider] = self._samples[provider][-self.window_size:]

    def record_sync(
        self,
        provider: str,
        model: str,
        duration_ms: float,
        success: bool = True,
    ) -> None:
        """Record a single latency measurement (sync-safe)."""
        sample = LatencySample(
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            success=success,
        )
        with self._sync_lock:
            self._samples.setdefault(provider, []).append(sample)
            # Trim to window size
            if len(self._samples[provider]) > self.window_size:
                self._samples[provider] = self._samples[provider][-self.window_size:]

    async def get_avg_latency_ms(self, provider: str) -> float | None:
        """Get the average successful latency for a provider in milliseconds.

        Returns None if no samples are available.
        """
        async with self._async_lock:
            samples = self._samples.get(provider, [])
            successful = [s for s in samples if s.success]
            if not successful:
                return None
            return sum(s.duration_ms for s in successful) / len(successful)

    async def get_error_rate(self, provider: str) -> float:
        """Get the error rate (0-1) for a provider."""
        async with self._async_lock:
            samples = self._samples.get(provider, [])
            if not samples:
                return 0.0
            errors = sum(1 for s in samples if not s.success)
            return errors / len(samples)

    async def get_ranking(self) -> list[dict[str, Any]]:
        """Return providers ranked by expected latency (fastest first).

        Only includes providers with at least one successful sample.
        """
        async with self._async_lock:
            rankings: list[dict[str, Any]] = []
            for provider, samples in self._samples.items():
                successful = [s for s in samples if s.success]
                if successful:
                    avg_ms = sum(s.duration_ms for s in successful) / len(successful)
                    error_rate = sum(1 for s in samples if not s.success) / len(samples)
                    rankings.append({
                        "provider": provider,
                        "avg_latency_ms": round(avg_ms, 1),
                        "sample_count": len(successful),
                        "error_rate": round(error_rate, 3),
                    })
            rankings.sort(key=lambda r: r["avg_latency_ms"])
            return rankings

    async def snapshot(self) -> dict[str, Any]:
        """Full snapshot of latency state."""
        return {
            "provider_rankings": await self.get_ranking(),
            "latencies": {
                prov: {
                    "avg_ms": await self.get_avg_latency_ms(prov),
                    "error_rate": await self.get_error_rate(prov),
                    "samples": len(samps),
                }
                for prov, samps in (await self._get_all_samples()).items()
            },
        }

    async def _get_all_samples(self) -> dict[str, list[LatencySample]]:
        async with self._async_lock:
            return dict(self._samples)


# ---------------------------------------------------------------------------
# Global latency tracker (single instance shared across all runs)
# ---------------------------------------------------------------------------

_latency_tracker = LatencyTracker()


def get_latency_tracker() -> LatencyTracker:
    """Get the global shared latency tracker."""
    return _latency_tracker


def get_fastest_provider(
    task_type: str = "interactive",
    preferred_providers: list[str] | None = None,
) -> str | None:
    """Determine the fastest provider for a given task type.

    Args:
        task_type: 'interactive' (prioritizes speed) or 'batch' (prioritizes cost)
        preferred_providers: Optional list of providers to constrain selection.
            If None, uses the configured provider_priority.

    Returns:
        Provider name string (e.g. 'groq', 'openai') or None if no data.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context — schedule the coroutine
            future = asyncio.run_coroutine_threadsafe(
                _resolve_fastest_provider(task_type, preferred_providers),
                loop,
            )
            return future.result(timeout=5)
        else:
            # No running loop — run synchronously
            return asyncio.run(
                _resolve_fastest_provider(task_type, preferred_providers)
            )
    except Exception as exc:
        logger.debug("Could not resolve fastest provider: %s", exc)
        return None


async def _resolve_fastest_provider(
    task_type: str,
    preferred_providers: list[str] | None,
) -> str | None:
    """Async implementation of fastest provider resolution."""
    ranking = await _latency_tracker.get_ranking()

    if not ranking:
        # No data yet — return the first preferred provider
        settings = load_settings()
        priority = preferred_providers or settings.models.provider_priority
        return priority[0] if priority else None

    # Filter to preferred providers if specified
    if preferred_providers:
        ranking = [r for r in ranking if r["provider"] in preferred_providers]

    if not ranking:
        return None

    if task_type == "interactive":
        # Return the fastest provider
        return ranking[0]["provider"]
    else:
        # For batch tasks, return a middle-ground provider (not the fastest,
        # not the slowest) to balance speed and cost
        mid_idx = len(ranking) // 2
        return ranking[mid_idx]["provider"]


# ---------------------------------------------------------------------------
# Context manager for timing LLM calls
# ---------------------------------------------------------------------------


@asynccontextmanager
async def track_latency(provider: str, model: str) -> AsyncIterator[None]:
    """Async context manager that records the latency of an LLM call.

    Usage:
        async with track_latency(provider, model):
            response = await litellm.acompletion(...)
    """
    start = time.monotonic()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        await _latency_tracker.record(provider, model, duration_ms, success)


@contextmanager
def track_latency_sync(provider: str, model: str) -> Iterator[None]:
    """Synchronous context manager that records the latency of an LLM call.

    Usage:
        with track_latency_sync(provider, model):
            response = litellm.completion(...)
    """
    start = time.monotonic()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        _latency_tracker.record_sync(provider, model, duration_ms, success)
