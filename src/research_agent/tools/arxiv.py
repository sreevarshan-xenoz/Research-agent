from __future__ import annotations

import os
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
        extract_pdf_text: bool | None = None,
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
        if extract_pdf_text is None:
            extract_pdf_text = os.getenv("ARXIV_EXTRACT_PDF_TEXT", "false").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        self._extract_pdf_text = extract_pdf_text

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

    def _parse_feed(self, xml_text: str) -> list[dict[str, Any]]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        items: list[dict[str, Any]] = []

        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            link = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            pdf_url = ""
            for link_tag in entry.findall("atom:link", ns):
                rel = str(link_tag.attrib.get("rel", "")).strip().lower()
                href = str(link_tag.attrib.get("href", "")).strip()
                if rel == "related" and href.endswith(".pdf"):
                    pdf_url = href
                    break

            content = ""
            if self._extract_pdf_text and pdf_url:
                content = self._extract_pdf_text_from_url(pdf_url)

            items.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": summary,
                    "content": content,
                    "pdf_url": pdf_url,
                    "published": published,
                    "source_type": "paper",
                    "provider": "arxiv",
                }
            )

        return items

    def _extract_pdf_text_from_url(self, pdf_url: str) -> str:
        try:
            response = self._client.get(pdf_url)
            response.raise_for_status()
            return self._extract_pdf_text_from_bytes(response.content)
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _extract_pdf_text_from_bytes(content: bytes) -> str:
        if not content:
            return ""
        try:
            import fitz  # PyMuPDF
        except Exception:  # noqa: BLE001
            return ""

        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                chunks: list[str] = []
                max_pages = min(len(doc), 3)
                for page_idx in range(max_pages):
                    text = (doc[page_idx].get_text("text") or "").strip()
                    if text:
                        chunks.append(text)
                return "\n".join(chunks)[:4000]
        except Exception:  # noqa: BLE001
            return ""
