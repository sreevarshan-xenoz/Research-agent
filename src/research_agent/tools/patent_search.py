from __future__ import annotations

from typing import Optional

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit
from research_agent.tools.rate_limiter import get_limiter


class PatentSearchAdapter(BaseToolAdapter):
    """Searches for patents related to research topics using public APIs (e.g., USPTO or similar).

    .. note::
        This adapter currently returns simulated results. Integration with a live
        patent API (e.g., USPTO, Google Patents, or Espacenet) is planned.
    """
    provider_name = "patent"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._limiter = get_limiter("patent")

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        # Returns simulated results until a real patent API integration is implemented.
        items = [
            {
                "title": f"Patent for {query} technique",
                "url": f"https://patents.google.com/?q={query}",
                "snippet": f"A novel method for implementing {query} in a scalable environment.",
                "authors": "Inventor et al.",
                "year": "2025",
                "publisher": "USPTO",
            }
        ]
        return ToolResult(
            provider=self.provider_name,
            items=items,
            warnings=["Patent search is currently in beta with simulated results."],
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        # search() is purely in-memory with no I/O, so call it directly.
        return self.search(query, limit)
