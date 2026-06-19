from __future__ import annotations

from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit, retry_with_backoff_sync


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
        self._client = client or httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "ResearchAgent/0.1 (research-agent; mailto:noreply@example.com)",
            },
        )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        params: dict[str, Any] = {
            "query": query,
            "limit": normalized_limit,
            "fields": "title,url,year,authors,citationCount,abstract,paperId,venue,publicationVenue,publicationTypes,externalIds,journal",
        }

        def _do_request() -> dict[str, Any]:
            resp = self._client.get(self._endpoint, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

        try:
            payload = retry_with_backoff_sync(_do_request, "semantic_scholar", api_key=self._api_key)
            items = [self._normalize_item(row) for row in payload.get("data", [])]
        except Exception as exc:
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"semantic_scholar_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    @staticmethod
    def _normalize_item(row: dict[str, Any]) -> dict[str, Any]:
        external_ids = row.get("externalIds") or {}
        doi = external_ids.get("DOI") or ""
        
        journal_info = row.get("journal") or {}
        journal_name = journal_info.get("name") or row.get("venue") or ""
        
        volume = journal_info.get("volume") or ""
        pages = journal_info.get("pages") or ""
        
        pub_venue = row.get("publicationVenue") or {}
        publisher = pub_venue.get("name") or ""
        
        pub_types = row.get("publicationTypes") or []
        doc_type = pub_types[0] if pub_types else ""
        
        journal = ""
        booktitle = ""
        if doc_type == "JournalArticle" or (not doc_type and journal_name):
            journal = journal_name
        elif doc_type in ("Conference", "Proceedings"):
            booktitle = journal_name
        else:
            if "proceedings" in journal_name.lower() or "conference" in journal_name.lower():
                booktitle = journal_name
            else:
                journal = journal_name

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
            "journal": journal,
            "booktitle": booktitle,
            "volume": str(volume),
            "number": "",
            "pages": pages,
            "doi": doi,
            "publisher": publisher,
            "type": doc_type,
        }
