import asyncio
import pytest


async def _reset_global_caches() -> None:
    """Reset all module-level caches to their initial empty state.

    Must be called outside the running event loop (e.g., from a sync fixture
    via asyncio.run()) to avoid interfering with pytest-asyncio's own loop.
    Each cache is cleared under its respective asyncio.Lock to avoid races.
    """
    from research_agent.orchestration.nodes.indexing import (
        _INDEX_CACHE,
        _INDEX_CACHE_LOCK,
        _INDEX_CACHE_TIMESTAMPS,
        _CONTRADICTION_CACHE,
        _CONTRADICTION_CACHE_LOCK,
        _INDEXED_TASKS_CACHE,
        _INDEXED_TASKS_CACHE_LOCK,
    )
    async with _INDEX_CACHE_LOCK:
        _INDEX_CACHE.clear()
        _INDEX_CACHE_TIMESTAMPS.clear()
    async with _CONTRADICTION_CACHE_LOCK:
        _CONTRADICTION_CACHE.clear()
    async with _INDEXED_TASKS_CACHE_LOCK:
        _INDEXED_TASKS_CACHE.clear()

    from research_agent.observability.logging import (
        _provider_failures,
        _provider_failures_lock,
        _node_timings,
        _node_timings_lock,
    )
    async with _provider_failures_lock:
        _provider_failures.clear()
    async with _node_timings_lock:
        _node_timings.clear()

    from research_agent.rag.indexer import (
        _GLOBAL_FINGERPRINT_CACHE,
        _FINGERPRINT_CACHE_LOCK,
    )
    async with _FINGERPRINT_CACHE_LOCK:
        _GLOBAL_FINGERPRINT_CACHE.clear()


def _sync_reset_global_caches() -> None:
    """Synchronous wrapper around _reset_global_caches for use from sync fixtures."""
    asyncio.run(_reset_global_caches())


@pytest.fixture(autouse=True)
def clean_global_caches():
    """Reset all global caches before and after every test.

    Prevents test-ordering-dependent failures caused by stale state in
    module-level caches (_INDEX_CACHE, _CONTRADICTION_CACHE,
    _INDEXED_TASKS_CACHE, _provider_failures, _node_timings,
    _GLOBAL_FINGERPRINT_CACHE).

    Uses a sync fixture (not async) so that asyncio.run() can create a fresh
    event loop for the cleanup coroutine, avoiding conflicts with
    pytest-asyncio's event loop in strict mode.
    """
    _sync_reset_global_caches()
    yield
    _sync_reset_global_caches()


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """
    Set isolated test environment: use in-memory Qdrant, clear API keys,
    and mock litellm calls so unit tests do not hang or conflict on file locks.
    """
    monkeypatch.setenv("QDRANT_LOCATION", ":memory:")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIMS_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    def _mock_completion(*args, **kwargs):
        raise ValueError("Litellm disabled during testing")
        
    async def _mock_acompletion(*args, **kwargs):
        raise ValueError("Litellm disabled during testing")
        
    try:
        import litellm
        monkeypatch.setattr(litellm, "completion", _mock_completion)
        monkeypatch.setattr(litellm, "acompletion", _mock_acompletion)
    except ImportError:
        pass
