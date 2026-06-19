from __future__ import annotations

import os
from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit, retry_with_backoff_sync


class OpenAlexAdapter(BaseToolAdapter):
    """Adapter for OpenAlex API (openalex.org) - a comprehensive catalog of papers."""
    provider_name = "openalex"

    def __init__(
        self,
        mailto: str | None = None,
        *,
        endpoint: str = "https://api.openalex.org/works",
        client: httpx.Client | None = None,
    ) -> None:
        self._mailto = mailto or os.getenv("CONTACT_EMAIL", "noreply@example.com")
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
        params: dict[str, Any] = {
            "search": query,
            "per_page": normalized_limit,
            "mailto": self._mailto,
        }

        def _do_request() -> dict[str, Any]:
            resp = self._client.get(self._endpoint, params=params)
            resp.raise_for_status()
            return resp.json()

        try:
            payload = retry_with_backoff_sync(_do_request, "openalex")
            items = [self._normalize_item(row) for row in payload.get("results", [])]
        except Exception as exc:
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"openalex_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

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

        primary_source = row.get("primary_location", {}).get("source", {}) if row.get("primary_location") else {}
        if not primary_source:
            primary_source = {}
        journal = ""
        booktitle = ""
        doc_type = row.get("type", "") or ""
        source_name = primary_source.get("display_name", "") or ""
        if doc_type == "journal-article":
            journal = source_name
        elif doc_type in ("proceedings-article", "conference-paper", "inproceedings"):
            booktitle = source_name
        else:
            if "proceedings" in source_name.lower() or "conference" in source_name.lower():
                booktitle = source_name
            else:
                journal = source_name

        biblio = row.get("biblio", {}) or {}
        volume = biblio.get("volume", "") or ""
        number = biblio.get("issue", "") or ""
        first_page = biblio.get("first_page", "") or ""
        last_page = biblio.get("last_page", "") or ""
        pages = ""
        if first_page and last_page:
            pages = f"{first_page}-{last_page}"
        elif first_page:
            pages = first_page

        publisher = primary_source.get("publisher", "") or row.get("publisher", "") or ""
        doi = row.get("doi", "") or ""
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]

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
            "journal": journal,
            "booktitle": booktitle,
            "volume": str(volume),
            "number": str(number),
            "pages": pages,
            "doi": doi,
            "publisher": publisher,
            "type": doc_type,
        }
