from __future__ import annotations

from typing import Any
import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class OpenAlexAdapter(BaseToolAdapter):
    """Adapter for OpenAlex API (openalex.org) - a comprehensive catalog of papers."""
    provider_name = "openalex"

    def __init__(
        self,
        mailto: str = "noreply@example.com",
        *,
        endpoint: str = "https://api.openalex.org/works",
        client: httpx.Client | None = None,
    ) -> None:
        self._mailto = mailto
        self._endpoint = endpoint
        self._client = client or httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": f"ResearchAgent/0.1 (research-agent; mailto:{mailto})",
            },
        )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        params = {
            "search": query,
            "per_page": normalized_limit,
            "mailto": self._mailto,
        }
        try:
            response = self._client.get(self._endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"openalex_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        items = [self._normalize_item(row) for row in payload.get("results", [])]
        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    @staticmethod
    def _normalize_item(row: dict[str, Any]) -> dict[str, Any]:
        """Normalize an OpenAlex result into our common format."""
        abstract_inverted = row.get("abstract_inverted_index")
        abstract = ""
        if abstract_inverted:
            # Reconstruct abstract from inverted index
            words = {}
            for word, indices in abstract_inverted.items():
                for idx in indices:
                    words[idx] = word
            sorted_indices = sorted(words.keys())
            abstract = " ".join(words[idx] for idx in sorted_indices)

        authorships = row.get("authorships", [])
        authors = [
            a.get("author", {}).get("display_name", "") 
            for a in authorships
        ]

        return {
            "title": row.get("display_name", ""),
            "url": row.get("doi") or row.get("ids", {}).get("openalex", ""),
            "snippet": abstract,
            "paper_id": row.get("id"),
            "year": row.get("publication_year"),
            "citation_count": row.get("cited_by_count"),
            "authors": authors,
            "source_type": "paper",
            "provider": "openalex",
        }
