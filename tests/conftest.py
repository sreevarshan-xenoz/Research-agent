import asyncio
import pytest





def _sync_clear_dict(d: dict) -> None:
    """Safely clear a dict without requiring async locks."""
    d.clear()


@pytest.fixture(autouse=True)
def clean_global_caches():
    """Reset all global caches before and after every test.

    Prevents test-ordering-dependent failures caused by stale state in
    module-level caches. Uses synchronous dict clears to avoid creating
    new event loops via asyncio.run(), which can conflict with
    pytest-asyncio on Windows.
    """
    from research_agent.orchestration.nodes.indexing import (
        _INDEX_CACHE,
        _INDEX_CACHE_TIMESTAMPS,
        _CONTRADICTION_CACHE,
        _INDEXED_TASKS_CACHE,
    )
    _sync_clear_dict(_INDEX_CACHE)
    _sync_clear_dict(_INDEX_CACHE_TIMESTAMPS)
    _sync_clear_dict(_CONTRADICTION_CACHE)
    _sync_clear_dict(_INDEXED_TASKS_CACHE)

    from research_agent.observability.logging import (
        _provider_failures,
        _node_timings,
    )
    _sync_clear_dict(_provider_failures)
    _sync_clear_dict(_node_timings)

    from research_agent.rag.indexer import _GLOBAL_FINGERPRINT_CACHE
    _sync_clear_dict(_GLOBAL_FINGERPRINT_CACHE)
    yield
    _sync_clear_dict(_INDEX_CACHE)
    _sync_clear_dict(_INDEX_CACHE_TIMESTAMPS)
    _sync_clear_dict(_CONTRADICTION_CACHE)
    _sync_clear_dict(_INDEXED_TASKS_CACHE)
    _sync_clear_dict(_provider_failures)
    _sync_clear_dict(_node_timings)
    _sync_clear_dict(_GLOBAL_FINGERPRINT_CACHE)


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """
    Set isolated test environment: use in-memory Qdrant, clear API keys,
    and mock agenerate_json/agenerate_text at the model layer so unit tests
    do not hang or conflict on file locks. Mocks at the higher level instead
    of litellm directly to avoid tenacity retry backoff delays (~6s per call).
    """
    monkeypatch.setenv("QDRANT_LOCATION", ":memory:")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIMS_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    # Mock all LLM functions at the model layer and in every module that
    # imports them via `from research_agent.models import agenerate_json`.
    # This is necessary because `from ... import ...` creates local bindings
    # at import time (during test collection), so monkeypatching the source
    # module doesn't propagate to consumer modules.
    async def _mock_json(*, role="head", prompt="", **kwargs):
        return None

    async def _mock_text(*, role="subagent", prompt="", **kwargs):
        return None

    def _mock_json_sync(*, role="head", prompt="", **kwargs):
        return None

    def _mock_text_sync(*, role="subagent", prompt="", **kwargs):
        return None

    # Patch source module
    import research_agent.models.llm_client
    monkeypatch.setattr(research_agent.models.llm_client, "agenerate_json", _mock_json)
    monkeypatch.setattr(research_agent.models.llm_client, "agenerate_text", _mock_text)
    monkeypatch.setattr(research_agent.models.llm_client, "generate_json", _mock_json_sync)
    monkeypatch.setattr(research_agent.models.llm_client, "generate_text", _mock_text_sync)

    import research_agent.models
    monkeypatch.setattr(research_agent.models, "agenerate_json", _mock_json)
    monkeypatch.setattr(research_agent.models, "agenerate_text", _mock_text)

    # Patch consumer modules at the source namespace.
    # The `from research_agent.models import agenerate_json` pattern creates local
    # bindings in each consumer module at import time. We need to override those
    # local bindings.
    import importlib
    _consumer_module_names = [
        "research_agent.orchestration.nodes.clarifier",
        "research_agent.orchestration.nodes.planner",
        "research_agent.orchestration.nodes.combiner",
        "research_agent.orchestration.nodes.composer",
        "research_agent.orchestration.nodes.replanner",
        "research_agent.orchestration.nodes.bias_detector",
        "research_agent.orchestration.nodes.comparison",
        "research_agent.orchestration.nodes.dataset_discovery",
        "research_agent.orchestration.nodes.figure_generator",
        "research_agent.orchestration.nodes.formula_normalizer",
        "research_agent.orchestration.nodes.formula_verifier",
        "research_agent.orchestration.nodes.future_work",
        "research_agent.orchestration.nodes.grant_proposal",
        "research_agent.orchestration.nodes.hallucination_guard",
        "research_agent.orchestration.nodes.knowledge_graph",
        "research_agent.orchestration.nodes.peer_reviewer",
        "research_agent.orchestration.nodes.code_execution",
        "research_agent.orchestration.survey",
        "research_agent.rag.table_extractor",
    ]
    for mod_name in _consumer_module_names:
        try:
            mod = importlib.import_module(mod_name)
            monkeypatch.setattr(mod, "agenerate_json", _mock_json)
            monkeypatch.setattr(mod, "agenerate_text", _mock_text)
        except Exception:
            pass
