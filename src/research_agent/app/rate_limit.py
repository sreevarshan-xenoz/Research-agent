"""Per-user and per-endpoint API rate limiting for P18 Security Hardening.

Uses a dual strategy:
1. **Per-user rate limiting**: Each authenticated user gets a token bucket
   based on their role (viewer/editor/admin).
2. **Per-endpoint overrides**: Specific paths can have custom limits.
3. **IP-based fallback**: Unauthenticated requests are limited by IP.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token bucket implementation
# ---------------------------------------------------------------------------


class TokenBucket:
    """Simple in-memory token bucket rate limiter.

    Thread-safe via asyncio.Lock. Suitable for single-process deployments.
    For multi-process deployments, swap for Redis-based implementation.
    """

    def __init__(self, rate: int, burst: int):
        """Initialize token bucket.

        Args:
            rate: Tokens replenished per minute.
            burst: Maximum burst size (initial tokens).
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket.

        Returns True if allowed, False if rate limited.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            # Refill tokens based on elapsed time
            refill = elapsed * (self._rate / 60.0)
            self._tokens = min(self._burst, self._tokens + refill)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        return self._tokens


# ---------------------------------------------------------------------------
# Rate limit store
# ---------------------------------------------------------------------------


class RateLimitStore:
    """In-memory store of token buckets keyed by user ID or IP.

    Auto-cleans buckets that haven't been used in 5 minutes.
    """

    def __init__(self):
        self._buckets: dict[str, tuple[TokenBucket, float]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = 300  # 5 minutes

    async def get_bucket(
        self,
        key: str,
        rate: int,
        burst: int,
    ) -> TokenBucket:
        """Get or create a token bucket for the given key."""
        async with self._lock:
            now = time.monotonic()
            if key in self._buckets:
                bucket, _ = self._buckets[key]
                self._buckets[key] = (bucket, now)
                return bucket

            bucket = TokenBucket(rate, burst)
            self._buckets[key] = (bucket, now)
            return bucket

    async def cleanup(self) -> int:
        """Remove stale buckets (not accessed in 5+ minutes).

        Returns number of buckets cleaned.
        """
        async with self._lock:
            now = time.monotonic()
            stale = [
                key for key, (_, last_access) in self._buckets.items()
                if now - last_access > self._cleanup_interval
            ]
            for key in stale:
                del self._buckets[key]
            return len(stale)


# Global rate limit store
_rate_limit_store = RateLimitStore()
_rate_limit_cleanup_task: asyncio.Task | None = None


async def _periodic_cleanup(interval: int = 300):
    """Periodically clean up stale rate limit buckets."""
    while True:
        await asyncio.sleep(interval)
        try:
            cleaned = await _rate_limit_store.cleanup()
            if cleaned:
                logger.debug("Rate limit cleanup: removed %d stale buckets", cleaned)
        except Exception as exc:
            logger.warning("Rate limit cleanup error: %s", exc)


def start_rate_limit_cleanup(interval: int = 300) -> asyncio.Task:
    """Start the background cleanup task for rate limit buckets."""
    global _rate_limit_cleanup_task
    if _rate_limit_cleanup_task is None or _rate_limit_cleanup_task.done():
        _rate_limit_cleanup_task = asyncio.create_task(_periodic_cleanup(interval))
    return _rate_limit_cleanup_task


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for per-user and per-endpoint rate limiting.

    Uses token bucket algorithm. Limits vary by user role:
    - Anonymous: configurable (default 60 req/min)
    - Authenticated viewers: configurable (default 300 req/min)
    - Editors/Admins: configurable (default 1000 req/min)

    Excludes health check and metrics endpoints.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_rpm: int = 60,
        auth_rpm: int = 300,
        admin_rpm: int = 1000,
        burst: int = 20,
        endpoint_overrides: dict[str, int] | None = None,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self._default_rpm = default_rpm
        self._auth_rpm = auth_rpm
        self._admin_rpm = admin_rpm
        self._burst = burst
        self._endpoint_overrides = endpoint_overrides or {}
        self._exclude_paths = set(exclude_paths or ["/health", "/metrics", "/api/health"])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip excluded paths
        for excluded in self._exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        # Determine rate limit tier
        method = request.method
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", None)

        # Check per-endpoint override first
        endpoint_key = f"{method}:{path}"
        if endpoint_key in self._endpoint_overrides:
            limit_rpm = self._endpoint_overrides[endpoint_key]
        else:
            # Choose limit based on user role
            if user_role == "admin":
                limit_rpm = self._admin_rpm
            elif user_id and user_role:
                limit_rpm = self._auth_rpm
            else:
                limit_rpm = self._default_rpm

        # Rate limit key: user ID if authenticated, otherwise IP
        if user_id:
            limit_key = f"user:{user_id}"
        else:
            ip = request.client.host if request.client else "unknown"
            limit_key = f"ip:{ip}"

        bucket = await _rate_limit_store.get_bucket(limit_key, limit_rpm, self._burst)
        allowed = await bucket.consume()

        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s (role=%s, path=%s, limit=%d rpm)",
                limit_key, user_role or "anonymous", path, limit_rpm,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {limit_rpm} requests per minute.",
                    "retry_after_seconds": 60 // max(1, limit_rpm),
                },
            )

        return await call_next(request)
