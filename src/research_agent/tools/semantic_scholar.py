from __future__ import annotations

from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class SemanticScholarAdapter(BaseToolAdapter):
    provider_name = "semantic_scholar"

    def __init__(
        self,
        api_key: str | None,
        *,
        endpoint: str = "https://api.semanticscholar.org/graph/v1/paper/search",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._client = client or httpx.Client(timeout=20)

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        params = {
            "query": query,
            "limit": normalized_limit,
            "fields": "title,url,year,authors,citationCount,abstract,paperId",
        }
        try:
            response = self._client.get(self._endpoint, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"semantic_scholar_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        items = [self._normalize_item(row) for row in payload.get("data", [])]
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
            "snippet": row.get("abstract", ""),
            "paper_id": row.get("paperId"),
            "year": row.get("year"),
            "citation_count": row.get("citationCount"),
            "authors": [author.get("name", "") for author in row.get("authors", [])],
            "source_type": "paper",
            "provider": "semantic_scholar",
        }
