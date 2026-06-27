from __future__ import annotations

import os
from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit
from research_agent.tools.rate_limiter import get_limiter, retry_with_backoff_sync


class PersonalLibraryAdapter(BaseToolAdapter):
    """Syncs with personal research libraries (Zotero, Mendeley) via API or local export."""
    provider_name = "personal_library"

    def __init__(self, zotero_api_key: str | None = None, zotero_user_id: str | None = None):
        self.api_key = zotero_api_key or os.getenv("ZOTERO_API_KEY")
        self.user_id = zotero_user_id or os.getenv("ZOTERO_USER_ID")
        self._limiter = get_limiter("personal_library")
        self._client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "ResearchAgent/0.1 (research-agent)"},
        )

    def _parse_entries(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in data:
            meta = entry.get("data", {})
            creators = meta.get("creators", [])
            authors = ", ".join(
                f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                for c in creators
            )
            items.append({
                "title": meta.get("title"),
                "url": meta.get("url"),
                "snippet": meta.get("abstractNote"),
                "authors": authors,
                "year": meta.get("date", "")[:4] if meta.get("date") else None,
                "publisher": meta.get("publicationTitle"),
            })
        return items

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)

        if not self.api_key or not self.user_id:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=["Zotero API key or User ID not configured. Personal library sync disabled."],
            )

        url = f"https://api.zotero.org/users/{self.user_id}/items?q={query}&limit={normalized_limit}&itemType=-attachment"
        headers = {"Zotero-API-Key": self.api_key}

        def _do_request() -> list[dict[str, Any]]:
            resp = self._client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

        try:
            data = retry_with_backoff_sync(_do_request, "personal_library")
            items = self._parse_entries(data)
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"Personal library sync failed: {str(e)}"],
            )

        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return await asyncio.to_thread(self.search, query, limit=limit)
