from __future__ import annotations

from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class OpenAlexAdapter(BaseToolAdapter):
    provider_name = "openalex"

    def __init__(
        self,
        *,
        endpoint: str = "https://api.openalex.org/works",
        client: httpx.Client | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._client = client or httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "ResearchAgent/0.1 (research-agent; mailto:noreply@example.com)",
            },
        )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        params = {
            "search": query,
            "per_page": normalized_limit,
        }
        try:
            response = self._client.get(self._endpoint, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"openalex_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        items = [self._normalize_item(row) for row in data.get("results", [])]
        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    @staticmethod
    def _decode_abstract(inverted_index: dict[str, list[int]] | None) -> str:
        if not inverted_index:
            return ""
        
        # OpenAlex uses inverted index for abstracts to comply with some legal restrictions
        # reconstructed_abstract = [None] * total_words
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        word_positions.sort()
        return " ".join(word for _, word in word_positions)

    def _normalize_item(self, row: dict[str, Any]) -> dict[str, Any]:
        abstract = self._decode_abstract(row.get("abstract_inverted_index"))
        return {
            "title": row.get("display_name", ""),
            "url": row.get("doi", row.get("id", "")),
            "snippet": abstract,
            "authors": [author.get("author", {}).get("display_name", "") for author in row.get("authorships", [])],
            "year": row.get("publication_year"),
            "citation_count": row.get("cited_by_count"),
            "source_type": "paper",
            "provider": "openalex",
        }
