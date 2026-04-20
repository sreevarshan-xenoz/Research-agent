from __future__ import annotations

import asyncio

import httpx
from bs4 import BeautifulSoup

from research_agent.tools.base import BaseToolAdapter, ToolResult


class PageFetcherAdapter(BaseToolAdapter):
    """Tool to fetch and clean full content from a URL."""
    provider_name = "page_fetcher"
    is_searcher = False

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
        )

    def search(self, query: str, limit: int = 1) -> ToolResult:
        """In this case, query is the URL."""
        url = query.strip()
        try:
            response = self._client.get(url)
            response.raise_for_status()
            content = self._clean_html(response.text)
            
            item = {
                "title": self._extract_title(response.text),
                "url": url,
                "content": content,
                "source_type": "web_page",
                "provider": self.provider_name,
            }
            return ToolResult(
                provider=self.provider_name,
                items=[item],
                metadata={"url": url},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"fetch_error:{type(exc).__name__}"],
                metadata={"url": url},
            )

    async def asearch(self, query: str, limit: int = 1) -> ToolResult:
        # Wrap the synchronous search for now, or use httpx.AsyncClient
        return await asyncio.to_thread(self.search, query, limit)

    def _clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for script_or_style in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script_or_style.decompose()

        # Get text
        text = soup.get_text(separator="\n")
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        return text[:15000]  # Limit content size for LLM context

    def _extract_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()
        return ""
