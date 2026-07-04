"""Shared rate limiting for all external providers.

Provides:
- Provider-specific quotas (configurable rates and bursts)
- Global registry that enforces limits across concurrent workers
- Per-provider metrics (request count, limit hits, retries, errors)
- Retry with exponential backoff + jitter
- Both sync and async acquire paths

Usage:
    limiter = get_limiter("arxiv")
    async with limiter:
        response = await client.get(...)
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

from aiolimiter import AsyncLimiter


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider Quota Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderQuota:
    """Rate limit configuration for a single provider."""
    max_rate: float          # Maximum requests per time_period
    time_period: float = 1.0  # Time window in seconds (default 1s)
    max_burst: int = 1        # Maximum burst size (aiolimiter uses this)
    retry_attempts: int = 3   # Number of retry attempts on rate-limit / transient errors
    retry_min_wait: float = 1.0   # Initial backoff seconds
    retry_max_wait: float = 30.0  # Maximum backoff seconds


# Known provider quotas (source: official docs / known rate limits)
# Conservative defaults — the goal is to avoid bans, not maximize throughput.
PROVIDER_QUOTAS: dict[str, ProviderQuota] = {
    # Paper APIs
    "arxiv": ProviderQuota(
        max_rate=1, time_period=3.0, max_burst=1,
        retry_attempts=3, retry_min_wait=2.0, retry_max_wait=30.0,
    ),
    "semantic_scholar": ProviderQuota(
        max_rate=1, time_period=1.0, max_burst=1,  # no-key default
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=15.0,
    ),
    "semantic_scholar_keyed": ProviderQuota(
        max_rate=10, time_period=1.0, max_burst=5,
        retry_attempts=3, retry_min_wait=0.5, retry_max_wait=10.0,
    ),
    "openalex": ProviderQuota(
        max_rate=10, time_period=1.0, max_burst=5,
        retry_attempts=3, retry_min_wait=0.5, retry_max_wait=10.0,
    ),
    "pubmed": ProviderQuota(
        max_rate=3, time_period=1.0, max_burst=2,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "pubmed_keyed": ProviderQuota(
        max_rate=10, time_period=1.0, max_burst=5,
        retry_attempts=3, retry_min_wait=0.5, retry_max_wait=15.0,
    ),
    "github": ProviderQuota(
        max_rate=5, time_period=1.0, max_burst=3,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "github_keyed": ProviderQuota(
        max_rate=30, time_period=1.0, max_burst=10,
        retry_attempts=3, retry_min_wait=0.5, retry_max_wait=15.0,
    ),
    "news_social": ProviderQuota(
        max_rate=2, time_period=1.0, max_burst=1,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=10.0,
    ),
    "patent": ProviderQuota(
        max_rate=3, time_period=1.0, max_burst=2,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=10.0,
    ),
    "personal_library": ProviderQuota(
        max_rate=5, time_period=1.0, max_burst=3,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=10.0,
    ),
    # Web search
    "tavily": ProviderQuota(
        max_rate=5, time_period=1.0, max_burst=3,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=15.0,
    ),
    "duckduckgo": ProviderQuota(
        max_rate=1, time_period=1.0, max_burst=1,
        retry_attempts=2, retry_min_wait=2.0, retry_max_wait=15.0,
    ),
    "page_fetcher": ProviderQuota(
        max_rate=5, time_period=1.0, max_burst=3,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=10.0,
    ),
    "browser_use": ProviderQuota(
        max_rate=2, time_period=1.0, max_burst=1,
        retry_attempts=2, retry_min_wait=2.0, retry_max_wait=20.0,
    ),
    "web_scrape": ProviderQuota(
        max_rate=3, time_period=1.0, max_burst=2,
        retry_attempts=2, retry_min_wait=1.0, retry_max_wait=15.0,
    ),
    # LLM providers
    "nvidia_llm": ProviderQuota(
        max_rate=10, time_period=1.0, max_burst=5,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "openrouter": ProviderQuota(
        max_rate=5, time_period=1.0, max_burst=3,
        retry_attempts=3, retry_min_wait=2.0, retry_max_wait=30.0,
    ),
    "ollama": ProviderQuota(
        max_rate=20, time_period=1.0, max_burst=10,
        retry_attempts=2, retry_min_wait=0.5, retry_max_wait=5.0,
    ),
    "vllm": ProviderQuota(
        max_rate=30, time_period=1.0, max_burst=15,
        retry_attempts=2, retry_min_wait=0.5, retry_max_wait=5.0,
    ),
    # New providers: OpenAI and Anthropic
    "openai_llm": ProviderQuota(
        max_rate=60, time_period=1.0, max_burst=20,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "anthropic_llm": ProviderQuota(
        max_rate=50, time_period=1.0, max_burst=10,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "gemini_llm": ProviderQuota(
        max_rate=60, time_period=1.0, max_burst=20,
        retry_attempts=3, retry_min_wait=1.0, retry_max_wait=30.0,
    ),
    "groq_llm": ProviderQuota(
        max_rate=30, time_period=1.0, max_burst=15,
        retry_attempts=3, retry_min_wait=0.5, retry_max_wait=15.0,
    ),
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class RateLimiterMetrics:
    """Exposed metrics for a single provider's rate limiter."""
    name: str
    requests_total: int = 0
    rate_limit_hits: int = 0
    retries_total: int = 0
    errors_total: int = 0
    success_total: int = 0
    last_request_ts: float = 0.0
    total_wait_seconds: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "requests_total": self.requests_total,
            "rate_limit_hits": self.rate_limit_hits,
            "retries_total": self.retries_total,
            "errors_total": self.errors_total,
            "success_total": self.success_total,
            "total_wait_seconds": round(self.total_wait_seconds, 3),
        }


# ---------------------------------------------------------------------------
# SharedRateLimiter
# ---------------------------------------------------------------------------

class SharedRateLimiter:
    """Dual-mode (sync + async) rate limiter with metrics and retry support.

    Thread-safe for sync calls; asyncio-safe for async calls.
    Uses aiolimiter.AsyncLimiter under the hood for async, and a
    time-based token bucket protected by threading.Lock for sync.
    """

    def __init__(self, quota: ProviderQuota, *, provider_name: str = "unknown") -> None:
        self._quota = quota
        self._async_limiter = AsyncLimiter(quota.max_rate, quota.time_period)
        self._sync_lock = threading.Lock()
        self._sync_interval = quota.time_period / quota.max_rate
        self._sync_last = 0.0
        self._metrics = RateLimiterMetrics(name=provider_name)
        self._active_limiter = quota  # store for access

    @property
    def metrics(self) -> RateLimiterMetrics:
        return self._metrics

    def sync_acquire(self) -> None:
        """Blocking acquire for synchronous call paths."""
        with self._sync_lock:
            now = time.monotonic()
            elapsed = now - self._sync_last
            if elapsed < self._sync_interval:
                wait = self._sync_interval - elapsed
                time.sleep(wait)
                self._metrics.total_wait_seconds += wait
            self._sync_last = time.monotonic()
        self._metrics.requests_total += 1
        self._metrics.last_request_ts = time.time()

    async def async_acquire(self) -> None:
        """Non-blocking acquire for async call paths (awaits token bucket)."""
        start = time.monotonic()
        await self._async_limiter.acquire()
        wait = time.monotonic() - start
        if wait > 0.01:
            self._metrics.rate_limit_hits += 1
        self._metrics.total_wait_seconds += wait
        self._metrics.requests_total += 1
        self._metrics.last_request_ts = time.time()

    def record_success(self) -> None:
        self._metrics.success_total += 1

    def record_error(self) -> None:
        self._metrics.errors_total += 1

    def record_retry(self) -> None:
        self._metrics.retries_total += 1

    @property
    def quota(self) -> ProviderQuota:
        return self._quota


# ---------------------------------------------------------------------------
# Global Registry
# ---------------------------------------------------------------------------

_registry: dict[str, SharedRateLimiter] = {}
_registry_lock = threading.Lock()


def get_limiter(name: str, api_key: str | None = None) -> SharedRateLimiter:
    """Get (or create) the shared rate limiter for a given provider name.

    Some providers have different quotas depending on whether an API key
    is present.  The caller passes ``api_key`` so the correct quota is
    selected on first creation.

    Returns the existing limiter if one has already been created for this name.
    """
    with _registry_lock:
        if name not in _registry:
            quota = _resolve_quota(name, api_key)
            _registry[name] = SharedRateLimiter(quota, provider_name=name)
        return _registry[name]


def _resolve_quota(name: str, api_key: str | None) -> ProviderQuota:
    """Select the right quota based on provider name and key presence."""
    has_key = bool(api_key and api_key.strip())

    keyed_variants = {
        "semantic_scholar": ("semantic_scholar", "semantic_scholar_keyed"),
        "pubmed": ("pubmed", "pubmed_keyed"),
        "github": ("github", "github_keyed"),
    }

    if name in keyed_variants and has_key:
        base, keyed = keyed_variants[name]
        return PROVIDER_QUOTAS.get(keyed, PROVIDER_QUOTAS[base])

    if name in PROVIDER_QUOTAS:
        return PROVIDER_QUOTAS[name]

    # Fallback: conservative default
    logger.warning("No quota configured for provider %r; using conservative default", name)
    return ProviderQuota(max_rate=1, time_period=2.0, max_burst=1)


def get_all_metrics() -> dict[str, dict[str, Any]]:
    """Snapshot metrics for every registered limiter."""
    with _registry_lock:
        return {name: limiter.metrics.snapshot() for name, limiter in _registry.items()}


def reset_all_metrics() -> None:
    """Reset all metrics counters (useful for testing)."""
    with _registry_lock:
        for name, limiter in _registry.items():
            limiter._metrics = RateLimiterMetrics(name=name)


# ---------------------------------------------------------------------------
# Retry Helper
# ---------------------------------------------------------------------------

async def retry_with_backoff(
    coro_factory: Any,
    provider_name: str,
    *,
    is_rate_limit: Any = None,
    api_key: str | None = None,
) -> Any:
    """Execute an async call with rate-limit-aware retry.

    ``coro_factory`` is a zero-argument callable (or async callable) that
    returns a coroutine (the actual API call).

    ``is_rate_limit`` is an optional callable ``exc -> bool`` that returns
    True if the exception indicates a rate limit (429 / too many requests).

    Respects the retry_attempts and backoff parameters from the provider quota.

    Returns the result of the coroutine, or raises the last exception on
    exhaustion.
    """
    limiter = get_limiter(provider_name, api_key)
    quota = limiter.quota
    last_exc: Exception | None = None

    for attempt in range(quota.retry_attempts):
        try:
            # Acquire rate limit token before each attempt
            await limiter.async_acquire()
            result = await coro_factory()
            limiter.record_success()
            return result
        except Exception as exc:
            last_exc = exc
            limiter.record_error()

            if attempt < quota.retry_attempts - 1:
                is_rate_limit_hit = is_rate_limit(exc) if is_rate_limit else _guess_rate_limit(exc)
                if is_rate_limit_hit:
                    limiter.metrics.rate_limit_hits += 1

                limiter.record_retry()
                base_wait = quota.retry_min_wait * (2 ** attempt)
                jitter = random.uniform(0, base_wait * 0.5)
                wait = min(base_wait + jitter, quota.retry_max_wait)
                logger.info(
                    "Retrying %s (attempt %d/%d) after %.1fs: %s",
                    provider_name, attempt + 1, quota.retry_attempts, wait, exc,
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    "%s exhausted %d retries: %s",
                    provider_name, quota.retry_attempts, exc,
                )

    raise last_exc  # type: ignore[misc]


def retry_with_backoff_sync(
    fn: Any,
    provider_name: str,
    *,
    is_rate_limit: Any = None,
    api_key: str | None = None,
) -> Any:
    """Synchronous version of retry_with_backoff.

    Uses the sync acquire path so it works in non-async contexts.
    """
    limiter = get_limiter(provider_name, api_key)
    quota = limiter.quota
    last_exc: Exception | None = None

    for attempt in range(quota.retry_attempts):
        try:
            limiter.sync_acquire()
            result = fn()
            limiter.record_success()
            return result
        except Exception as exc:
            last_exc = exc
            limiter.record_error()

            if attempt < quota.retry_attempts - 1:
                is_rate_limit_hit = is_rate_limit(exc) if is_rate_limit else _guess_rate_limit(exc)
                if is_rate_limit_hit:
                    limiter.metrics.rate_limit_hits += 1

                limiter.record_retry()
                base_wait = quota.retry_min_wait * (2 ** attempt)
                jitter = random.uniform(0, base_wait * 0.5)
                wait = min(base_wait + jitter, quota.retry_max_wait)
                logger.info(
                    "Retrying %s (attempt %d/%d) after %.1fs: %s",
                    provider_name, attempt + 1, quota.retry_attempts, wait, exc,
                )
                time.sleep(wait)
            else:
                logger.warning(
                    "%s exhausted %d retries: %s",
                    provider_name, quota.retry_attempts, exc,
                )

    raise last_exc  # type: ignore[misc]


def _guess_rate_limit(exc: Exception) -> bool:
    """Heuristic check for common rate-limit indicators."""
    msg = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status and status == 429:
        return True
    return any(
        keyword in msg
        for keyword in ["rate limit", "too many requests", "429", "retry later", "throttled"]
    )
