from __future__ import annotations

import os

from research_agent.config.schema import AppSettings
from research_agent.tools.arxiv import ArxivAdapter
from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.semantic_scholar import SemanticScholarAdapter
from research_agent.tools.web_search import WebSearchAdapter


def build_tool_registry(settings: AppSettings) -> dict[str, BaseToolAdapter]:
    registry: dict[str, BaseToolAdapter] = {}

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
    results: dict[str, ToolResult] = {}
    for provider_name, adapter in registry.items():
        results[provider_name] = adapter.search(query, limit=limit)
    return results
