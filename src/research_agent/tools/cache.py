from __future__ import annotations

import json
import hashlib
from typing import Any, Optional
import redis.asyncio as redis

from research_agent.config import load_settings
from research_agent.tools.base import ToolResult

class GlobalToolCache:
    """Redis-backed global cache for tool results to avoid redundant API calls."""
    
    def __init__(self):
        settings = load_settings()
        self.enabled = settings.features.session_persistence == "redis"
        self.url = settings.redis.url
        self.ttl = 3600 * 24 # 24 hours
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    def _get_key(self, provider: str, query: str, limit: int) -> str:
        query_hash = hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()
        return f"research_agent:cache:{provider}:{query_hash}:{limit}"

    async def get(self, provider: str, query: str, limit: int) -> Optional[ToolResult]:
        if not self.enabled:
            return None
            
        try:
            client = await self._get_client()
            key = self._get_key(provider, query, limit)
            data = await client.get(key)
            if data:
                payload = json.loads(data)
                return ToolResult(**payload)
        except Exception:
            pass
        return None

    async def set(self, provider: str, query: str, limit: int, result: ToolResult) -> None:
        if not self.enabled or not result.items:
            return
            
        try:
            client = await self._get_client()
            key = self._get_key(provider, query, limit)
            # Only cache if no errors
            if not any("error" in w.lower() for w in result.warnings):
                payload = {
                    "provider": result.provider,
                    "items": result.items,
                    "warnings": result.warnings,
                    "metadata": result.metadata
                }
                await client.set(key, json.dumps(payload), ex=self.ttl)
        except Exception:
            pass

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

_GLOBAL_CACHE = GlobalToolCache()

async def get_cached_tool_result(provider: str, query: str, limit: int) -> Optional[ToolResult]:
    return await _GLOBAL_CACHE.get(provider, query, limit)

async def set_cached_tool_result(provider: str, query: str, limit: int, result: ToolResult) -> None:
    await _GLOBAL_CACHE.set(provider, query, limit, result)
