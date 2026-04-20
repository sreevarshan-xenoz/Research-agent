from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from research_agent.config.schema import AppSettings
from research_agent.tools.arxiv import ArxivAdapter
from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.browser_use import BrowserUseAdapter
from research_agent.tools.open_alex import OpenAlexAdapter
from research_agent.tools.page_fetcher import PageFetcherAdapter
from research_agent.tools.semantic_scholar import SemanticScholarAdapter
from research_agent.tools.web_search import DuckDuckGoAdapter, WebSearchAdapter


def build_tool_registry(settings: AppSettings) -> dict[str, BaseToolAdapter]:
    registry: dict[str, BaseToolAdapter] = {
        "page_fetcher": PageFetcherAdapter(),
    }

    web_provider = settings.retrieval.web_provider
    if web_provider == "browser_use":
        registry["browser_use"] = BrowserUseAdapter()
    elif web_provider == "duckduckgo":
        registry["duckduckgo"] = DuckDuckGoAdapter()
    elif web_provider == "hybrid":
        registry["browser_use"] = BrowserUseAdapter()
        registry["duckduckgo"] = DuckDuckGoAdapter()
    elif web_provider == "scrape":
        registry["web_scrape"] = BrowserUseAdapter(
            browser_enabled=False,
            provider_name="web_scrape",
        )
    else:
        registry["web_search"] = WebSearchAdapter(api_key=os.getenv("TAVILY_API_KEY"))

    if "arxiv" in settings.retrieval.paper_providers:
        registry["arxiv"] = ArxivAdapter()
    if "semantic_scholar" in settings.retrieval.paper_providers:
        registry["semantic_scholar"] = SemanticScholarAdapter(
            api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        )
    if "openalex" in settings.retrieval.paper_providers:
        registry["openalex"] = OpenAlexAdapter()

    return registry


def run_multi_source_search(
    query: str,
    registry: dict[str, BaseToolAdapter],
    *,
    limit: int = 5,
) -> dict[str, ToolResult]:
    """Run searches across all providers in parallel."""
    results: dict[str, ToolResult] = {}

    with ThreadPoolExecutor(max_workers=len(registry) or 1) as executor:
        # Create a mapping of future to provider name
        future_to_provider = {
            executor.submit(adapter.search, query, limit=limit): name
            for name, adapter in registry.items()
            if getattr(adapter, "is_searcher", True)
        }

        for future in future_to_provider:
            provider_name = future_to_provider[future]
            try:
                results[provider_name] = future.result()
            except Exception as e:
                # Return an empty result with warning on failure
                results[provider_name] = ToolResult(
                    provider=provider_name,
                    items=[],
                    warnings=[f"Parallel search failed: {str(e)}"]
                )

    return results


async def arun_multi_source_search(
    query: str,
    registry: dict[str, BaseToolAdapter],
    *,
    limit: int = 5,
    providers: list[str] | None = None,
) -> dict[str, ToolResult]:
    """Run searches across all providers in parallel using asyncio."""
    
    async def _safe_search(name: str, adapter: BaseToolAdapter) -> tuple[str, ToolResult]:
        try:
            res = await adapter.asearch(query, limit=limit)
            return name, res
        except Exception as e:
            return name, ToolResult(
                provider=name,
                items=[],
                warnings=[f"Async search failed: {str(e)}"]
            )

    tasks = []
    for name, adapter in registry.items():
        if not getattr(adapter, "is_searcher", True):
            continue
        if providers and name not in providers and adapter.provider_name not in providers:
            continue
        tasks.append(_safe_search(name, adapter))

    if not tasks:
        return {}
        
    outputs = await asyncio.gather(*tasks)
    return {name: res for name, res in outputs}
