from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import os
import re
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


@dataclass
class _SearchCandidate:
    title: str
    url: str
    snippet: str


class BrowserUseAdapter(BaseToolAdapter):
    """Browser-first web retrieval with HTTP scraping fallback.

    Retrieval strategy:
    1. browser-use SDK agent run (repo-native integration).
    2. Playwright browser automation fallback.
    3. HTTP scraping fallback to keep retrieval working when browser automation fails.
    """

    provider_name = "browser_use"

    def __init__(
        self,
        *,
        search_base_url: str = "https://duckduckgo.com/html/",
        browser_enabled: bool = True,
        provider_name: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._search_base_url = search_base_url
        self._browser_enabled = browser_enabled
        self._provider_name = provider_name or self.provider_name
        self._client = client or httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
        )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)
        warnings: list[str] = []
        items: list[dict[str, Any]] = []
        browser_method = "disabled" if not self._browser_enabled else "none"

        browser_candidates: list[_SearchCandidate] = []
        if self._browser_enabled:
            try:
                browser_candidates, browser_method = self._search_with_browser(query, normalized_limit)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"browser_use_error:{type(exc).__name__}")

        for candidate in browser_candidates:
            items.append(self._to_item(candidate, source_type="browser"))
            if len(items) >= normalized_limit:
                break

        if len(items) < normalized_limit:
            try:
                scraping_candidates = self._search_with_scraping(query, normalized_limit)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"web_scraping_error:{type(exc).__name__}")
                scraping_candidates = []

            seen_urls = {str(item.get("url", "")) for item in items}
            for candidate in scraping_candidates:
                if candidate.url in seen_urls:
                    continue
                items.append(self._to_item(candidate, source_type="web_scrape"))
                seen_urls.add(candidate.url)
                if len(items) >= normalized_limit:
                    break

        return ToolResult(
            provider=self._provider_name,
            items=items,
            warnings=warnings,
            metadata={
                "query": query,
                "limit": normalized_limit,
                "raw_count": len(items),
                "browser_enabled": self._browser_enabled,
                "browser_method": browser_method,
                "browser_count": len([item for item in items if item["source_type"] == "browser"]),
                "scrape_count": len([item for item in items if item["source_type"] == "web_scrape"]),
            },
        )

    def _search_with_browser(self, query: str, limit: int) -> tuple[list[_SearchCandidate], str]:
        try:
            return self._search_with_browser_use_sdk(query, limit), "browser_use_sdk"
        except Exception:  # noqa: BLE001
            pass

        return self._search_with_playwright(query, limit), "playwright"

    def _search_with_browser_use_sdk(self, query: str, limit: int) -> list[_SearchCandidate]:
        try:
            from browser_use import Agent, Browser, ChatBrowserUse, ChatOpenAI
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("browser_use_sdk_not_available") from exc

        llm = self._build_browser_use_llm(ChatBrowserUse=ChatBrowserUse, ChatOpenAI=ChatOpenAI)
        if llm is None:
            raise RuntimeError("browser_use_llm_not_configured")

        task = (
            f"Search the web for '{query}'. "
            f"Return ONLY a JSON array with up to {limit} objects. "
            "Each object must include: title, url, snippet. No markdown, no explanation."
        )

        max_steps = max(8, min(12, limit * 3))

        # Disable default extensions to avoid unstable Chrome extension flags in some environments.
        browser = Browser(headless=True, enable_default_extensions=False)
        agent = Agent(task=task, llm=llm, browser=browser, use_vision=False)
        history = agent.run_sync(max_steps=max_steps)

        if hasattr(history, "final_result"):
            raw_output = history.final_result()
        else:
            raw_output = str(history)

        candidates = self._parse_browser_use_candidates(raw_output, limit=limit)
        if not candidates:
            raise RuntimeError("browser_use_empty_result")
        return candidates

    def _search_with_playwright(self, query: str, limit: int) -> list[_SearchCandidate]:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("playwright_not_available") from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(
                f"https://duckduckgo.com/?q={quote_plus(query)}",
                wait_until="domcontentloaded",
                timeout=12000,
            )
            rendered_html = page.content()
            browser.close()

        candidates = self._extract_search_candidates(rendered_html, limit=limit)
        if not candidates:
            raise RuntimeError("playwright_empty_result")
        return candidates

    def _build_browser_use_llm(self, *, ChatBrowserUse, ChatOpenAI):  # noqa: ANN001, ANN202
        api_key = os.getenv("BROWSER_USE_API_KEY")
        if api_key:
            model = os.getenv("BROWSER_USE_MODEL", "bu-2-0")
            return ChatBrowserUse(model=model)

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        key = openrouter_key or openai_key
        if not key:
            return None

        kwargs: dict[str, Any] = {
            "model": os.getenv("BROWSER_USE_OPENAI_MODEL")
            or os.getenv("LITELLM_DEFAULT_MODEL")
            or "gpt-4.1-mini",
            "api_key": key,
        }
        if openrouter_key:
            kwargs["base_url"] = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        elif os.getenv("OPENAI_API_BASE"):
            kwargs["base_url"] = os.getenv("OPENAI_API_BASE")

        return ChatOpenAI(**kwargs)

    def _parse_browser_use_candidates(self, raw_output: Any, *, limit: int) -> list[_SearchCandidate]:
        text = str(raw_output or "").strip()
        if not text:
            return []

        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            match = re.search(r"\[.*\]", text, flags=re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:  # noqa: BLE001
                    parsed = None

        if not isinstance(parsed, list):
            return []

        candidates: list[_SearchCandidate] = []
        for row in parsed:
            if not isinstance(row, dict):
                continue
            title = self._clean_text(str(row.get("title", "")))
            url = str(row.get("url", "")).strip()
            snippet = self._clean_text(str(row.get("snippet", "")))
            if not title or not url:
                continue
            candidates.append(_SearchCandidate(title=title, url=url, snippet=snippet))
            if len(candidates) >= limit:
                break

        return candidates

    def _search_with_scraping(self, query: str, limit: int) -> list[_SearchCandidate]:
        response = self._client.get(self._search_base_url, params={"q": query})
        response.raise_for_status()
        candidates = self._extract_search_candidates(response.text, limit=limit)

        enriched: list[_SearchCandidate] = []
        for candidate in candidates:
            snippet = candidate.snippet
            if not snippet:
                snippet = self._fetch_page_snippet(candidate.url)
            enriched.append(_SearchCandidate(title=candidate.title, url=candidate.url, snippet=snippet))
        return enriched

    def _extract_search_candidates(self, html_text: str, *, limit: int) -> list[_SearchCandidate]:
        soup = BeautifulSoup(html_text, "html.parser")
        candidates: list[_SearchCandidate] = []

        selectors = ["a.result__a", "article h2 a", "h2 a"]
        for selector in selectors:
            anchors = soup.select(selector)
            if anchors:
                for anchor in anchors:
                    href = str(anchor.get("href") or "").strip()
                    title = self._clean_text(anchor.get_text(" ", strip=True))
                    if not href or not title:
                        continue

                    snippet = ""
                    container = anchor.find_parent(["article", "div", "li"])
                    if container is not None:
                        snippet_el = container.select_one(".result__snippet, .snippet, p")
                        if snippet_el is not None:
                            snippet = self._clean_text(snippet_el.get_text(" ", strip=True))

                    candidates.append(_SearchCandidate(title=title, url=href, snippet=snippet))
                    if len(candidates) >= limit:
                        return candidates
                if candidates:
                    return candidates

        return candidates

    def _fetch_page_snippet(self, url: str) -> str:
        try:
            response = self._client.get(url, follow_redirects=True)
            response.raise_for_status()
        except Exception:  # noqa: BLE001
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        meta_description = soup.find("meta", attrs={"name": "description"})
        if meta_description and meta_description.get("content"):
            return self._clean_text(str(meta_description.get("content")))[:400]

        body = soup.get_text(" ", strip=True)
        return self._clean_text(body)[:400]

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(unescape(value).split())

    @staticmethod
    def _to_item(candidate: _SearchCandidate, *, source_type: str) -> dict[str, Any]:
        return {
            "title": candidate.title,
            "url": candidate.url,
            "snippet": candidate.snippet,
            "score": None,
            "source_type": source_type,
        }
