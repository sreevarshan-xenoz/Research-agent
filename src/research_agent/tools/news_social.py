from __future__ import annotations

import aiohttp
from typing import Optional

from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff

class NewsSocialAdapter(BaseToolAdapter):
    """Fetches real-time technical news and social signals (Hacker News, Reddit)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.provider_name = "news_social"
        self._limiter = get_limiter("news_social")

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        # We'll search Hacker News Algolia API as a primary source of high-signal tech news
        url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={limit}"
        
        async def _do_request() -> ToolResult:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            provider=self.provider_name,
                            items=[],
                            warnings=[f"HN API returned status {resp.status}"]
                        )
                    
                    data = await resp.json()
                    items = []
                    for hit in data.get("hits", []):
                        items.append({
                            "title": hit.get("title"),
                            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            "snippet": f"Points: {hit.get('points')} | Comments: {hit.get('num_comments')}",
                            "authors": hit.get("author"),
                            "year": hit.get("created_at", "")[:4] if hit.get("created_at") else None,
                        })
                    
                    return ToolResult(
                        provider=self.provider_name,
                        items=items
                    )

        try:
            return await retry_with_backoff(_do_request, "news_social")
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"News search failed: {str(e)}"]
            )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return asyncio.run(self.asearch(query, limit))
