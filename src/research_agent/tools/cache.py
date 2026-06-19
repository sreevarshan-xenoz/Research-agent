from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as redis

from research_agent.config import load_settings
from research_agent.tools.base import ToolResult


logger = logging.getLogger(__name__)


class GlobalToolCache:
    """Redis-backed global cache for tool results to avoid redundant API calls."""

    def __init__(self):
        settings = load_settings()
        self.enabled = settings.features.session_persistence == "redis"
        self.url = settings.redis.url
        self.ttl = 3600 * 24  # 24 hours
        self.timeout = settings.redis.timeout_seconds
        self._client: Optional[redis.Redis] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:  # Double-check under lock
                    # Try to use the shared Redis pool from graph.py first.
                    # Import lazily to avoid circular import (graph -> nodes -> tools).
                    from research_agent.orchestration.graph import get_redis_pool

                    shared_pool = get_redis_pool()
                    if shared_pool is not None:
                        self._client = redis.Redis(
                            connection_pool=shared_pool,
                            decode_responses=True,
                        )
                        logger.info("Tool cache using shared Redis pool")
                    else:
                        self._client = redis.from_url(
                            self.url,
                            decode_responses=True,
                            socket_connect_timeout=self.timeout,
                            socket_timeout=self.timeout,
                            retry_on_timeout=True,
                            health_check_interval=30,
                        )
                    try:
                        await self._client.ping()  # type: ignore[misc]
                        logger.info("Tool cache Redis client ready: %s", self.url)
                    except Exception:
                        logger.warning(
                            "Tool cache Redis ping failed (cache disabled): %s",
                            self.url,
                        )
                        self._client = None
                        raise
        return self._client

    def _get_key(self, provider: str, query: str, limit: int) -> str:
        query_hash = hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()
        return f"research_agent:cache:{provider}:{query_hash}:{limit}"

    async def get(self, provider: str, query: str, limit: int) -> Optional[ToolResult]:
        if not self.enabled:
            return None

        for attempt in range(2):
            try:
                client = await self._get_client()
                key = self._get_key(provider, query, limit)
                data = await client.get(key)
                if data:
                    payload = json.loads(data)
                    return ToolResult(**payload)
                return None
            except Exception as exc:
                if attempt == 0:
                    logger.warning("Redis cache get failed, retrying: %s", exc)
                    await asyncio.sleep(0.5)
                    # Reset client so _get_client reconnects on next attempt
                    self._client = None
                else:
                    logger.exception("Redis cache get failed after retry")
                    return None
        return None

    async def set(self, provider: str, query: str, limit: int, result: ToolResult) -> None:
        if not self.enabled or not result.items:
            return

        for attempt in range(2):
            try:
                client = await self._get_client()
                key = self._get_key(provider, query, limit)
                if not any("error" in w.lower() for w in result.warnings):
                    payload = {
                        "provider": result.provider,
                        "items": result.items,
                        "warnings": result.warnings,
                        "metadata": result.metadata,
                    }
                    await client.set(key, json.dumps(payload), ex=self.ttl)
                return
            except Exception as exc:
                if attempt == 0:
                    logger.warning("Redis cache set failed, retrying: %s", exc)
                    await asyncio.sleep(0.5)
                    self._client = None
                else:
                    logger.warning("Redis cache set failed after retry: %s", exc)
                    return

    async def close(self):
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("Tool cache Redis client closed")
            except Exception:
                logger.exception("Error closing tool cache Redis client")
            finally:
                self._client = None


_GLOBAL_CACHE = GlobalToolCache()


async def get_cached_tool_result(provider: str, query: str, limit: int) -> Optional[ToolResult]:
    return await _GLOBAL_CACHE.get(provider, query, limit)


async def set_cached_tool_result(provider: str, query: str, limit: int, result: ToolResult) -> None:
    await _GLOBAL_CACHE.set(provider, query, limit, result)


async def close_global_tool_cache() -> None:
    """Close the global tool cache Redis connection. Idempotent — safe to call multiple times."""
    await _GLOBAL_CACHE.close()
