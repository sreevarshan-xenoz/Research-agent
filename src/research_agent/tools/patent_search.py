from __future__ import annotations

from typing import Optional

from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff

class PatentSearchAdapter(BaseToolAdapter):
    """Searches for patents related to research topics using public APIs (e.g., USPTO or similar)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.provider_name = "patent"
        self._limiter = get_limiter("patent")

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        async def _do_request() -> ToolResult:
            items = [
                {
                    "title": f"Patent for {query} technique",
                    "url": f"https://patents.google.com/?q={query}",
                    "snippet": f"A novel method for implementing {query} in a scalable environment.",
                    "authors": "Inventor et al.",
                    "year": "2025",
                    "publisher": "USPTO"
                }
            ]
            return ToolResult(
                provider=self.provider_name,
                items=items,
                warnings=["Patent search is currently in beta with simulated results."]
            )

        try:
            return await retry_with_backoff(_do_request, "patent")
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"Patent search failed: {str(e)}"]
            )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return asyncio.run(self.asearch(query, limit))
