from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff_sync


class GitHubCrawlerAdapter(BaseToolAdapter):
    """Searches for and summarizes GitHub repositories related to research topics."""
    provider_name = "github"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GITHUB_TOKEN")
        self._limiter = get_limiter("github", self.api_key)
        self._client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ResearchAgent/0.1",
            },
        )

    def _search_url(self, query: str, limit: int) -> str:
        search_query = query
        if "github" not in query.lower() and "code" not in query.lower():
            search_query = f"{query} implementation"
        return f"https://api.github.com/search/repositories?q={search_query}&per_page={limit}"

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.api_key:
            headers["Authorization"] = f"token {self.api_key}"
        return headers

    def _parse_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for repo in data.get("items", []):
            items.append({
                "title": repo.get("full_name"),
                "url": repo.get("html_url"),
                "snippet": repo.get("description"),
                "stars": repo.get("stargazers_count"),
                "language": repo.get("language"),
                "updated_at": repo.get("updated_at"),
                "year": repo.get("updated_at", "")[:4] if repo.get("updated_at") else None,
            })
        return items

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        url = self._search_url(query, normalized_limit)
        headers = self._build_headers()

        def _do_request() -> dict[str, Any]:
            resp = self._client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

        try:
            data = retry_with_backoff_sync(_do_request, "github", api_key=self.api_key)
            items = self._parse_response(data)
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"GitHub search failed: {str(e)}"],
            )

        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return await asyncio.to_thread(self.search, query, limit=limit)
