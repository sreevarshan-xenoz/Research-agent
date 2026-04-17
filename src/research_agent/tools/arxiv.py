from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class ArxivAdapter(BaseToolAdapter):
    provider_name = "arxiv"

    def __init__(
        self,
        *,
        endpoint: str = "http://export.arxiv.org/api/query",
        client: httpx.Client | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._client = client or httpx.Client(timeout=20)

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": normalized_limit,
        }
        try:
            response = self._client.get(self._endpoint, params=params)
            response.raise_for_status()
            items = self._parse_feed(response.text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"arxiv_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

        return ToolResult(
            provider=self.provider_name,
            items=items,
            metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
        )

    @staticmethod
    def _parse_feed(xml_text: str) -> list[dict[str, Any]]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        items: list[dict[str, Any]] = []

        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            link = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            items.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": summary,
                    "published": published,
                    "source_type": "paper",
                    "provider": "arxiv",
                }
            )

        return items
