from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from research_agent.config.loader import load_settings
from research_agent.output.latex.renderer import build_bibtex, render_main_tex
from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.tools.registry import run_multi_source_search, arun_multi_source_search
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


def test_config_loader_overrides(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
runtime:
  mode: api_only
  max_iterations: 2
  max_runtime_minutes: 10
  max_cost_usd: 1.0
  interactive_checkpoints: false
models:
  worker_model: old-worker
  strong_model: old-strong
output:
  default_template: ieee
  default_acm_layout: sigconf
  supported_templates:
    - ieee
    - acm
retrieval:
  web_provider: tavily
  paper_providers:
    - arxiv
  allow_metadata_fallback: true
  metadata_fallback_confidence_penalty: 0.1
""".strip(),
        encoding="utf-8",
    )

    env = {
        "INTERACTIVE_CHECKPOINTS": "true",
        "DEFAULT_ACM_LAYOUT": "manuscript",
    }
    settings = load_settings(settings_path=settings_file, env=env)

    assert settings.runtime.interactive_checkpoints is True
    assert settings.output.default_acm_layout == "manuscript"


def test_granular_bibtex_generation() -> None:
    citations = [
        {
            "key": "ref1",
            "title": "Journal Paper Title",
            "author": "Author A",
            "year": "2024",
            "journal": "Nature Journal",
            "volume": "12",
            "number": "3",
            "pages": "100-110",
            "doi": "10.1038/nature",
            "type": "journal-article",
        },
        {
            "key": "ref2",
            "title": "Conference Paper Title",
            "author": "Author B",
            "year": "2023",
            "booktitle": "IEEE Conference on AI",
            "pages": "45-50",
            "publisher": "IEEE",
            "type": "proceedings-article",
        },
        {
            "key": "ref3",
            "title": "A Great Book",
            "author": "Author C",
            "year": "2022",
            "publisher": "O'Reilly",
            "volume": "1",
            "type": "book",
        },
        {
            "key": "ref4",
            "title": "An arXiv Preprint",
            "author": "Author D",
            "year": "2025",
            "url": "https://arxiv.org/abs/2501.0001",
            "type": "preprint",
        },
        {
            "key": "ref5",
            "title": "A Phd Thesis",
            "author": "Author E",
            "year": "2020",
            "publisher": "Stanford University",
            "type": "phdthesis",
        },
        {
            "key": "ref6",
            "title": "Technical Report",
            "author": "Author F",
            "year": "2021",
            "publisher": "MIT",
            "number": "MIT-TR-45",
            "type": "techreport",
        }
    ]

    bibtex = build_bibtex(citations)
    
    assert "@article{ref1," in bibtex
    assert "journal = {Nature Journal}," in bibtex
    assert "volume = {12}," in bibtex
    assert "number = {3}," in bibtex
    assert "pages = {100-110}," in bibtex
    assert "doi = {10.1038/nature}," in bibtex

    assert "@inproceedings{ref2," in bibtex
    assert "booktitle = {IEEE Conference on AI}," in bibtex
    assert "pages = {45-50}," in bibtex
    assert "publisher = {IEEE}," in bibtex

    assert "@book{ref3," in bibtex
    assert "publisher = {O'Reilly}," in bibtex
    assert "volume = {1}," in bibtex

    assert "@misc{ref4," in bibtex
    assert "howpublished = {\\url{https://arxiv.org/abs/2501.0001}}," in bibtex

    assert "@phdthesis{ref5," in bibtex
    assert "school = {Stanford University}," in bibtex

    assert "@techreport{ref6," in bibtex
    assert "institution = {MIT}," in bibtex
    assert "number = {MIT-TR-45}," in bibtex


class FakeFailingWebSearch(BaseToolAdapter):
    provider_name = "tavily"
    is_searcher = True

    def __init__(self, api_key=None):
        pass

    def search(self, query: str, limit: int = 5) -> ToolResult:
        return ToolResult(
            provider="tavily",
            warnings=["web_search_error:HTTPStatusError"],
            items=[],
        )


def test_web_search_failover_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "research_agent.tools.web_search.DuckDuckGoAdapter.search",
        lambda *args, **kwargs: ToolResult(
            provider="duckduckgo",
            items=[{"title": "DDG Result", "url": "https://ddg.com", "snippet": "DDG"}]
        )
    )

    registry = {
        "web_search": FakeFailingWebSearch(api_key=None),
    }

    # Verify run_multi_source_search failover
    res = run_multi_source_search("test query", registry, limit=2)
    assert "web_search" in res
    assert len(res["web_search"].items) == 1
    assert res["web_search"].items[0]["title"] == "DDG Result"
    assert res["web_search"].provider == "duckduckgo"


@pytest.mark.asyncio
async def test_web_search_failover_async_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "research_agent.tools.web_search.DuckDuckGoAdapter.search",
        lambda *args, **kwargs: ToolResult(
            provider="duckduckgo",
            items=[{"title": "DDG Result", "url": "https://ddg.com", "snippet": "DDG"}]
        )
    )

    registry = {
        "web_search": FakeFailingWebSearch(api_key=None),
    }

    # Verify arun_multi_source_search failover
    res = await arun_multi_source_search("test query", registry, limit=2)
    assert "web_search" in res
    assert len(res["web_search"].items) == 1
    assert res["web_search"].items[0]["title"] == "DDG Result"
    assert res["web_search"].provider == "duckduckgo"


@pytest.mark.asyncio
async def test_interactive_checkpoint_and_resume(monkeypatch) -> None:
    from research_agent.config.schema import AppSettings, RuntimeSettings, OutputSettings
    
    original_settings = load_settings()
    
    mocked_settings = AppSettings(
        runtime=RuntimeSettings(
            mode="api_only",
            max_iterations=1,
            max_runtime_minutes=5,
            max_cost_usd=1.0,
            interactive_checkpoints=True,
        ),
        models=original_settings.models,
        output=OutputSettings(
            default_template="acm",
            default_acm_layout="sigconf",
            supported_templates=["acm", "ieee"],
        ),
        retrieval=original_settings.retrieval,
        features=original_settings.features,
    )
    
    monkeypatch.setattr("research_agent.config.load_settings", lambda *args, **kwargs: mocked_settings)

    state = WorkflowState(
        run_id="test-checkpoint-run-001",
        topic="CRISPR delivery mechanisms in therapeutic applications",
        template="acm",
        autonomy_mode="hybrid",
        max_iterations=1,
    )

    # First run to trigger plan validation checkpoint pause
    res1 = await run_graph(state, registry={})
    
    assert res1.phase == "awaiting_plan_approval"
    assert res1.stop_reason == "plan_validation_checkpoint"
    assert len(res1.tasks) > 0
    
    # Modify task title
    res1.tasks[0].title = "User Edited Title"
    
    # Resume the graph
    res2 = await run_graph(res1, registry={})
    
    print(f"DEBUG: res2.phase = {res2.phase}")
    print(f"DEBUG: res2.stop_reason = {res2.stop_reason}")
    print(f"DEBUG: res2.tasks = {res2.tasks}")
    print(f"DEBUG: res2.run_warnings = {res2.run_warnings}")
    
    # Check that graph resumed past the checkpoint
    assert res2.phase != "awaiting_plan_approval"
    assert res2.stop_reason != "plan_validation_checkpoint"
    assert res2.tasks[0].title == "User Edited Title"
