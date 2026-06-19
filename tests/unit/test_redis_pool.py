"""Tests for Redis pool creation, retry logic, and lifecycle management.

Covers:
- _create_redis_pool (success / retry / exhaustion)
- get_redis_pool (returns None or pool)
- close_redis_pool (clears pool, idempotent)
- get_memory_diagnostics (structure when pool absent)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from research_agent.orchestration.graph import (
    _create_redis_pool,
    close_redis_pool,
    get_memory_diagnostics,
    get_redis_pool,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_redis_pool():
    """Ensure _redis_pool starts as None and is restored after each test."""
    import research_agent.orchestration.graph as gm

    before = gm._redis_pool
    gm._redis_pool = None
    yield
    gm._redis_pool = before


def _mock_redis_infra(monkeypatch, *, pool=None, ping_ok=True) -> MagicMock:
    """Install mocks for ``redis.ConnectionPool.from_url`` and ``redis.Redis``.

    Returns the mock client so callers can assert on it.
    """
    mock_pool = pool or MagicMock()
    mock_client = MagicMock()
    mock_client.ping = AsyncMock() if ping_ok else AsyncMock(side_effect=ConnectionError("ping failed"))
    mock_client.aclose = AsyncMock()

    monkeypatch.setattr(
        "research_agent.orchestration.graph.redis.ConnectionPool.from_url",
        lambda *a, **kw: mock_pool,
    )
    monkeypatch.setattr(
        "research_agent.orchestration.graph.redis.Redis",
        lambda *a, **kw: mock_client,
    )
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    return mock_client


# ---------------------------------------------------------------------------
# _create_redis_pool
# ---------------------------------------------------------------------------

class TestCreateRedisPool:
    """_create_redis_pool — pool creation with 3-attempt retry."""

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        """Returns pool when Redis is reachable on first attempt."""
        mock_pool = MagicMock()
        client = _mock_redis_infra(monkeypatch, pool=mock_pool, ping_ok=True)

        pool = await _create_redis_pool("redis://localhost:6379", 10, 5)

        assert pool is mock_pool
        client.ping.assert_awaited_once()
        client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self, monkeypatch):
        """Success after 2 failures — retry count is correct."""
        mock_pool = MagicMock()
        call_count = 0

        def from_url_side_effect(*_a, **_kw):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"attempt {call_count} refused")
            return mock_pool

        mock_client = MagicMock()
        mock_client.ping = AsyncMock()
        mock_client.aclose = AsyncMock()

        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.ConnectionPool.from_url",
            from_url_side_effect,
        )
        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.Redis",
            lambda *a, **kw: mock_client,
        )
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        pool = await _create_redis_pool("redis://localhost:6379", 10, 5)

        assert pool is mock_pool
        assert call_count == 3
        mock_client.ping.assert_awaited_once()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, monkeypatch):
        """Raises ConnectionError after 3 consecutive failures."""
        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.ConnectionPool.from_url",
            lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("down")),
        )
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        with pytest.raises(ConnectionError, match="Could not connect to Redis after 3 attempts"):
            await _create_redis_pool("redis://localhost:6379", 10, 5)

    @pytest.mark.asyncio
    async def test_ping_failure_triggers_retry(self, monkeypatch):
        """A ping failure on the probed connection also triggers a retry."""
        call_count = 0
        mock_pool = MagicMock()

        def from_url_side_effect(*_a, **_kw):
            nonlocal call_count
            call_count += 1
            return mock_pool

        mock_client = MagicMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("ping timeout"))
        mock_client.aclose = AsyncMock()

        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.ConnectionPool.from_url",
            from_url_side_effect,
        )
        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.Redis",
            lambda *a, **kw: mock_client,
        )
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        with pytest.raises(ConnectionError, match="Could not connect to Redis after 3 attempts"):
            await _create_redis_pool("redis://localhost:6379", 10, 5)

        assert call_count == 3  # Pool was created 3 times but ping failed each time

    @pytest.mark.asyncio
    async def test_retry_wait_is_exponential(self, monkeypatch):
        """The sleep duration increases with each retry attempt."""
        sleeps: list[float] = []
        mock_pool = MagicMock()
        call_count = 0

        def from_url_side_effect(*_a, **_kw):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"attempt {call_count} refused")
            return mock_pool

        async def fake_sleep(seconds: float):
            sleeps.append(seconds)

        mock_client = MagicMock()
        mock_client.ping = AsyncMock()
        mock_client.aclose = AsyncMock()

        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.ConnectionPool.from_url",
            from_url_side_effect,
        )
        monkeypatch.setattr(
            "research_agent.orchestration.graph.redis.Redis",
            lambda *a, **kw: mock_client,
        )
        monkeypatch.setattr("asyncio.sleep", fake_sleep)

        await _create_redis_pool("redis://localhost:6379", 10, 5)

        # Base waits: 2^0 + jitter ≈ 1, 2^1 + jitter ≈ 2, 2^2 + jitter ≈ 4
        # After 2 failures, we sleep twice (attempt 0 and 1),
        # then succeed on attempt 2 with no sleep
        assert len(sleeps) == 2
        assert 1.0 <= sleeps[0] < 3.0  # 2^0 + uniform(0,1)
        assert 2.0 <= sleeps[1] < 5.0  # 2^1 + uniform(0,1)


# ---------------------------------------------------------------------------
# get_redis_pool
# ---------------------------------------------------------------------------

class TestGetRedisPool:
    """get_redis_pool — read the module-level pool reference."""

    def test_returns_none_initially(self):
        """Returns None when no pool has been created."""
        assert get_redis_pool() is None

    def test_returns_pool_when_set(self, monkeypatch):
        """Returns the pool reference after it has been assigned."""
        mock_pool = MagicMock()
        monkeypatch.setattr("research_agent.orchestration.graph._redis_pool", mock_pool)
        assert get_redis_pool() is mock_pool


# ---------------------------------------------------------------------------
# close_redis_pool
# ---------------------------------------------------------------------------

class TestCloseRedisPool:
    """close_redis_pool — graceful shutdown, idempotent."""

    @pytest.mark.asyncio
    async def test_disconnects_and_clears_pool(self, monkeypatch):
        """Disconnects the pool and sets module-level _redis_pool to None."""
        mock_pool = MagicMock()
        mock_pool.disconnect = AsyncMock()

        monkeypatch.setattr("research_agent.orchestration.graph._redis_pool", mock_pool)

        await close_redis_pool()

        assert get_redis_pool() is None
        mock_pool.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_error_does_not_raise(self, monkeypatch):
        """An error during pool.disconnect() is logged but not propagated."""
        mock_pool = MagicMock()
        mock_pool.disconnect = AsyncMock(side_effect=RuntimeError("connection lost"))

        monkeypatch.setattr("research_agent.orchestration.graph._redis_pool", mock_pool)

        # Should not raise
        await close_redis_pool()

        assert get_redis_pool() is None

    @pytest.mark.asyncio
    async def test_idempotent_when_already_none(self):
        """Calling close_redis_pool when pool is already None is a no-op."""
        # The fixture already sets _redis_pool = None
        await close_redis_pool()  # Should not raise
        assert get_redis_pool() is None

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self, monkeypatch):
        """Calling close_redis_pool twice does not error."""
        mock_pool = MagicMock()
        mock_pool.disconnect = AsyncMock()

        monkeypatch.setattr("research_agent.orchestration.graph._redis_pool", mock_pool)

        await close_redis_pool()
        # Second call — pool is now None
        await close_redis_pool()

        assert get_redis_pool() is None
        mock_pool.disconnect.assert_awaited_once()  # Only called once


# ---------------------------------------------------------------------------
# get_memory_diagnostics
# ---------------------------------------------------------------------------

class TestGetMemoryDiagnostics:
    """get_memory_diagnostics — structure and content."""

    @pytest.mark.asyncio
    async def test_redis_pool_not_initialized(self):
        """Reports redis_pool.initialized=False when no pool exists."""
        diag = await get_memory_diagnostics()
        pool_info = diag.get("redis_pool", {})
        assert pool_info.get("initialized") is False

    @pytest.mark.asyncio
    async def test_redis_pool_initialized(self, monkeypatch):
        """Reports redis_pool.initialized=True and max_connections when pool exists."""
        mock_pool = MagicMock()
        mock_pool.max_connections = 15
        monkeypatch.setattr("research_agent.orchestration.graph._redis_pool", mock_pool)

        diag = await get_memory_diagnostics()

        pool_info = diag.get("redis_pool", {})
        assert pool_info.get("initialized") is True
        assert pool_info.get("max_connections") == 15

    @pytest.mark.asyncio
    async def test_contains_index_cache_keys(self):
        """Diagnostics dict includes index/contradiction/tasks cache keys."""
        diag = await get_memory_diagnostics()
        # These should always be present (may be 0)
        assert "index_cache_runs" in diag
        assert "contradiction_cache_runs" in diag
        assert "indexed_tasks_cache_runs" in diag

    @pytest.mark.asyncio
    async def test_contains_other_cache_keys(self):
        """Diagnostics dict includes fingerprint and JWT cache keys."""
        diag = await get_memory_diagnostics()
        assert "fingerprint_cache_size" in diag
        assert "jwt_secret_cached" in diag
