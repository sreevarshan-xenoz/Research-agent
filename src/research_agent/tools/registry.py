from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from research_agent.config.schema import AppSettings
from research_agent.tools.arxiv import ArxivAdapter
from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.browser_use import BrowserUseAdapter
from research_agent.tools.semantic_scholar import SemanticScholarAdapter
from research_agent.tools.web_search import WebSearchAdapter


def build_tool_registry(settings: AppSettings) -> dict[str, BaseToolAdapter]:
    registry: dict[str, BaseToolAdapter] = {}

    web_provider = settings.retrieval.web_provider
    if web_provider == "browser_use":
        registry["browser_use"] = BrowserUseAdapter()
    elif web_provider == "hybrid":
        registry["browser_use"] = BrowserUseAdapter()
        registry["web_search"] = WebSearchAdapter(api_key=os.getenv("TAVILY_API_KEY"))
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
