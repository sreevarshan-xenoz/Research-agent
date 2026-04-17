from __future__ import annotations

from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class WebSearchAdapter(BaseToolAdapter):
    provider_name = "web_search"

    def __init__(
        self,
        api_key: str | None,
        *,
        endpoint: str = "https://api.tavily.com/search",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._client = client or httpx.Client(timeout=20)

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        if not self._api_key:
            return ToolResult(
                provider=self.provider_name,
                warnings=["missing_tavily_api_key"],
                metadata={"query": query, "limit": normalized_limit},
            )

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": normalized_limit,
            "search_depth": "advanced",
        }
        try:
            response = self._client.post(self._endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"web_search_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        items = [self._normalize_item(row) for row in data.get("results", [])]
        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    @staticmethod
    def _normalize_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": row.get("title", ""),
            "url": row.get("url", ""),
            "snippet": row.get("content", ""),
            "score": row.get("score"),
            "source_type": "web",
        }
