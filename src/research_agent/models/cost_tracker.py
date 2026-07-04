"""Cost tracking and budget enforcement for multi-provider LLM usage.

Tracks per-model and per-run token usage and cost, enforces budget caps,
and provides metrics for cost-aware routing decisions.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost model: known per-1K-token prices (USD) for common models.
# Sources: official pricing pages (OpenAI, Anthropic, Google, Groq, etc.)
# Fallback uses a conservative estimate for unknown models.
# ---------------------------------------------------------------------------

# Input (prompt) cost per 1K tokens
_INPUT_COST_PER_1K: dict[str, float] = {
    # OpenAI
    "gpt-4o": 0.0025,
    "gpt-4o-mini": 0.00015,
    "gpt-4-turbo": 0.01,
    "gpt-3.5-turbo": 0.0015,
    # Anthropic
    "claude-3-5-sonnet": 0.003,
    "claude-3-haiku": 0.00025,
    "claude-3-opus": 0.015,
    # Google Gemini
    "gemini-2.0-flash": 0.0001,
    "gemini-2.0-pro": 0.002,
    "gemini-1.5-pro": 0.00125,
    # Groq
    "llama-3.3-70b": 0.00059,
    "llama-3.1-8b": 0.00005,
    "mixtral-8x7b": 0.00024,
    # NVIDIA
    "llama-3.1-405b": 0.003,
    "kimi-k2": 0.002,
    # Ollama (local, free)
    "ollama": 0.0,
}

# Output (completion) cost per 1K tokens
_OUTPUT_COST_PER_1K: dict[str, float] = {
    "gpt-4o": 0.01,
    "gpt-4o-mini": 0.0006,
    "gpt-4-turbo": 0.03,
    "gpt-3.5-turbo": 0.002,
    "claude-3-5-sonnet": 0.015,
    "claude-3-haiku": 0.00125,
    "claude-3-opus": 0.075,
    "gemini-2.0-flash": 0.0004,
    "gemini-2.0-pro": 0.008,
    "gemini-1.5-pro": 0.005,
    "llama-3.3-70b": 0.00079,
    "llama-3.1-8b": 0.0001,
    "mixtral-8x7b": 0.00041,
    "llama-3.1-405b": 0.004,
    "kimi-k2": 0.008,
    "ollama": 0.0,
}

_FALLBACK_COST = 0.001  # Conservative default per 1K tokens


def _normalize_model_key(model_name: str) -> str:
    """Extract a recognizable model key from a full model path.

    E.g. 'openai/gpt-4o' -> 'gpt-4o'
         'anthropic/claude-3-5-sonnet-20241022' -> 'claude-3-5-sonnet'
         'gemini/gemini-2.0-flash' -> 'gemini-2.0-flash'
         'groq/llama-3.3-70b-versatile' -> 'llama-3.3-70b'
         'ollama/qwen3:8b' -> 'ollama'
    """
    # Strip provider prefix
    short = model_name.split("/")[-1] if "/" in model_name else model_name
    # Check known keys by prefix matching
    for known_key in _INPUT_COST_PER_1K:
        if short.startswith(known_key):
            return known_key
    # Check if it's ollama/local
    if "ollama" in model_name.lower() or "qwen" in model_name.lower() or "deepseek-r1" in short.lower():
        return "ollama"
    return short


def estimate_cost(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    """Estimate the cost of a model invocation in USD.

    Uses known pricing tables. Falls back to a conservative estimate
    for unknown models.
    """
    key = _normalize_model_key(model_name)
    input_cost = _INPUT_COST_PER_1K.get(key, _FALLBACK_COST)
    output_cost = _OUTPUT_COST_PER_1K.get(key, _FALLBACK_COST * 4)  # Output typically 4x input
    cost = (input_tokens / 1000 * input_cost) + (output_tokens / 1000 * output_cost)
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Per-run cost accumulator
# ---------------------------------------------------------------------------

@dataclass
class CostEntry:
    """A single cost record for a model invocation."""
    model: str
    provider: str
    task_type: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


class RunCostTracker:
    """Tracks cumulative cost for a single research run.

    Thread-safe (uses asyncio.Lock) so multiple concurrent workers
    can safely record costs in parallel.
    """

    def __init__(self, run_id: str, budget_usd: float = 5.0):
        self.run_id = run_id
        self.budget_usd = budget_usd
        self._entries: list[CostEntry] = []
        self._total_cost: float = 0.0
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def record(
        self,
        model: str,
        provider: str,
        task_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float | None = None,
    ) -> float:
        """Record a cost entry (async-safe). If cost_usd is None, estimate from tokens.

        Returns the cumulative cost after this entry.
        """
        if cost_usd is None:
            cost_usd = estimate_cost(model, input_tokens, output_tokens)

        entry = CostEntry(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        async with self._async_lock:
            self._entries.append(entry)
            self._total_cost += cost_usd
            return self._total_cost

    def record_sync(
        self,
        model: str,
        provider: str,
        task_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float | None = None,
    ) -> float:
        """Synchronous version of record() for use from sync call paths.

        Uses a threading.Lock instead of asyncio.Lock.
        """
        if cost_usd is None:
            cost_usd = estimate_cost(model, input_tokens, output_tokens)

        entry = CostEntry(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        with self._sync_lock:
            self._entries.append(entry)
            self._total_cost += cost_usd
            return self._total_cost

    @property
    async def total_cost(self) -> float:
        async with self._async_lock:
            return round(self._total_cost, 6)

    @property
    async def is_over_budget(self) -> bool:
        async with self._async_lock:
            return self._total_cost >= self.budget_usd

    async def budget_remaining(self) -> float:
        async with self._async_lock:
            return round(max(0.0, self.budget_usd - self._total_cost), 6)

    async def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of current cost metrics."""
        async with self._async_lock:
            return {
                "run_id": self.run_id,
                "budget_usd": self.budget_usd,
                "total_cost_usd": round(self._total_cost, 6),
                "over_budget": self._total_cost >= self.budget_usd,
                "remaining_usd": round(max(0.0, self.budget_usd - self._total_cost), 6),
                "call_count": len(self._entries),
                "entries": [
                    {
                        "model": e.model,
                        "provider": e.provider,
                        "task_type": e.task_type,
                        "input_tokens": e.input_tokens,
                        "output_tokens": e.output_tokens,
                        "cost_usd": e.cost_usd,
                        "timestamp": e.timestamp,
                    }
                    for e in self._entries
                ],
            }


# ---------------------------------------------------------------------------
# Global active trackers
# ---------------------------------------------------------------------------

_active_trackers: dict[str, RunCostTracker] = {}
_active_trackers_async_lock = asyncio.Lock()
_active_trackers_sync_lock = threading.Lock()


async def get_cost_tracker(run_id: str, budget_usd: float = 5.0) -> RunCostTracker:
    """Get (or create) a cost tracker for the given run (async-safe)."""
    async with _active_trackers_async_lock:
        if run_id not in _active_trackers:
            _active_trackers[run_id] = RunCostTracker(run_id, budget_usd)
        return _active_trackers[run_id]


def get_cost_tracker_sync(run_id: str, budget_usd: float = 5.0) -> RunCostTracker:
    """Get (or create) a cost tracker for the given run (sync-safe)."""
    with _active_trackers_sync_lock:
        if run_id not in _active_trackers:
            _active_trackers[run_id] = RunCostTracker(run_id, budget_usd)
        return _active_trackers[run_id]


async def remove_cost_tracker(run_id: str) -> None:
    """Remove and finalize a cost tracker (called at run end)."""
    async with _active_trackers_async_lock:
        _active_trackers.pop(run_id, None)


def remove_cost_tracker_sync(run_id: str) -> None:
    """Synchronous version of remove_cost_tracker."""
    with _active_trackers_sync_lock:
        _active_trackers.pop(run_id, None)


async def get_all_cost_metrics() -> dict[str, dict[str, Any]]:
    """Aggregate cost metrics across all active runs."""
    async with _active_trackers_async_lock:
        metrics: dict[str, dict[str, Any]] = {}
        for run_id, tracker in _active_trackers.items():
            async with tracker._async_lock:
                metrics[run_id] = {
                    "total_cost_usd": tracker._total_cost,
                    "budget_usd": tracker.budget_usd,
                    "call_count": len(tracker._entries),
                }
        return metrics


def get_all_cost_metrics_sync() -> dict[str, dict[str, Any]]:
    """Synchronous version of get_all_cost_metrics."""
    with _active_trackers_sync_lock:
        metrics: dict[str, dict[str, Any]] = {}
        for run_id, tracker in _active_trackers.items():
            with tracker._sync_lock:
                metrics[run_id] = {
                    "total_cost_usd": tracker._total_cost,
                    "budget_usd": tracker.budget_usd,
                    "call_count": len(tracker._entries),
                }
        return metrics
