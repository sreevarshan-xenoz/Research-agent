from __future__ import annotations

from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff_sync


class NewsSocialAdapter(BaseToolAdapter):
    """Fetches real-time technical news and social signals (Hacker News, Reddit)."""
    provider_name = "news_social"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._limiter = get_limiter("news_social")
        self._client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "ResearchAgent/0.1 (research-agent)"},
        )

    def _parse_hits(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for hit in data.get("hits", []):
            items.append({
                "title": hit.get("title"),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "snippet": f"Points: {hit.get('points')} | Comments: {hit.get('num_comments')}",
                "authors": hit.get("author"),
                "year": hit.get("created_at", "")[:4] if hit.get("created_at") else None,
            })
        return items

    def search(self, query: str, limit: int = 5) -> ToolResult:
        """Search Hacker News Algolia API for technical news."""
        normalized_limit = safe_limit(limit)
        url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={normalized_limit}"

        def _do_request() -> dict[str, Any]:
            resp = self._client.get(url)
            resp.raise_for_status()
            return resp.json()

        try:
            data = retry_with_backoff_sync(_do_request, "news_social")
            items = self._parse_hits(data)
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"News search failed: {str(e)}"],
            )

        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return await asyncio.to_thread(self.search, query, limit=limit)
