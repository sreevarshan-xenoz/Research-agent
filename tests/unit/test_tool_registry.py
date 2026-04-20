from __future__ import annotations

from research_agent.config.schema import AppSettings
from research_agent.tools import ArxivAdapter, DuckDuckGoAdapter, OpenAlexAdapter, SemanticScholarAdapter
from research_agent.tools.registry import build_tool_registry


def _settings(web_provider: str = "duckduckgo") -> AppSettings:
    return AppSettings.model_validate(
        {
            "runtime": {
                "mode": "api_only",
                "max_iterations": 4,
                "max_runtime_minutes": 25,
                "max_cost_usd": 0,
            },
            "models": {
                "worker_model": "local/fallback-worker",
                "strong_model": "local/fallback-strong",
            },
            "output": {
                "default_template": "ieee",
                "supported_templates": ["ieee", "acm"],
            },
            "retrieval": {
                "web_provider": web_provider,
                "paper_providers": ["arxiv", "semantic_scholar", "openalex"],
                "allow_metadata_fallback": True,
                "metadata_fallback_confidence_penalty": 0.15,
            },
        }
    )


def test_registry_builds_free_first_retrieval_stack() -> None:
    registry = build_tool_registry(_settings())

    assert isinstance(registry["duckduckgo"], DuckDuckGoAdapter)
    assert isinstance(registry["arxiv"], ArxivAdapter)
    assert isinstance(registry["semantic_scholar"], SemanticScholarAdapter)
    assert isinstance(registry["openalex"], OpenAlexAdapter)
    assert registry["page_fetcher"].is_searcher is False


def test_hybrid_registry_stays_free_first() -> None:
    registry = build_tool_registry(_settings(web_provider="hybrid"))

    assert "browser_use" in registry
    assert "duckduckgo" in registry
    assert "web_search" not in registry
