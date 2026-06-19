import pytest
from research_agent.rag.indexer import LRUCache, ResearchIndex, reset_fingerprint_cache


@pytest.mark.asyncio
async def test_research_index_deduplicates_repeated_chunks() -> None:
    index = ResearchIndex(collection_name="test_dedup")

    item = {
        "title": "Same Source",
        "url": "https://example.com/source",
        "snippet": "Repeated evidence sentence. Repeated evidence sentence.",
        "year": "2026",
    }

    await index.aadd_finding("t1", "web", item)
    await index.aadd_finding("t2", "web", item)

    stats = index.get_stats()
    assert stats["inserted_points"] >= 1
    assert stats["skipped_duplicates"] >= 1
    index.close()


# ---------------------------------------------------------------------------
# ResearchIndex.close() — idempotency and safety
# ---------------------------------------------------------------------------

class TestResearchIndexClose:
    """ResearchIndex.close() — safe to call multiple times."""

    def test_close_is_idempotent(self) -> None:
        """Calling close() twice does not raise."""
        index = ResearchIndex(collection_name="test_close_idem")
        index.close()  # first call
        index.close()  # second call — should be safe

    @pytest.mark.asyncio
    async def test_close_after_indexing(self) -> None:
        """close() after adding findings does not raise."""
        index = ResearchIndex(collection_name="test_close_after")
        item = {
            "snippet": "Some research content for close test.",
            "url": "https://example.com/close-test",
        }
        await index.aadd_finding("t1", "web", item)
        # close after data has been upserted
        index.close()

    def test_close_sync_is_not_async(self) -> None:
        """close() is a sync method and returns None."""
        import inspect
        index = ResearchIndex(collection_name="test_close_sync")
        assert not inspect.iscoroutinefunction(index.close)
        assert index.close() is None


# ---------------------------------------------------------------------------
# reset_fingerprint_cache() — global dedup cache lifecycle
# ---------------------------------------------------------------------------

class TestResetFingerprintCache:
    """reset_fingerprint_cache() — clears the cross-run dedup cache."""

    @pytest.fixture(autouse=True)
    def _reset_after(self) -> None:
        """Reset the global cache after each test so state doesn't leak."""
        yield
        import asyncio
        asyncio.run(reset_fingerprint_cache())

    @pytest.mark.asyncio
    async def test_reset_clears_entries(self, monkeypatch) -> None:
        """Entries added to the global cache are gone after reset."""
        # Replace global cache with a fresh empty one
        from research_agent.rag.indexer import LRUCache
        fresh_cache = LRUCache(capacity=50000)
        monkeypatch.setattr("research_agent.rag.indexer._GLOBAL_FINGERPRINT_CACHE", fresh_cache)

        index = ResearchIndex(collection_name="test_fp_clear")
        item1 = {"snippet": "Fingerprint cache content A", "url": "https://test/fp-a"}
        item2 = {"snippet": "Fingerprint cache content B", "url": "https://test/fp-b"}
        await index.aadd_finding("t1", "web", item1)
        await index.aadd_finding("t2", "web", item2)
        index.close()

        assert len(fresh_cache) > 0

        await reset_fingerprint_cache()

        # After reset, the module-level _GLOBAL_FINGERPRINT_CACHE is fresh
        import research_agent.rag.indexer as idx_mod
        assert len(idx_mod._GLOBAL_FINGERPRINT_CACHE) == 0

    @pytest.mark.asyncio
    async def test_reset_is_idempotent(self) -> None:
        """Calling reset_fingerprint_cache() multiple times is safe."""
        await reset_fingerprint_cache()  # first
        await reset_fingerprint_cache()  # second — should not raise

    @pytest.mark.asyncio
    async def test_new_cache_has_correct_capacity(self, monkeypatch) -> None:
        """The new LRUCache created by reset has the expected capacity."""
        monkeypatch.setattr("research_agent.rag.indexer._GLOBAL_FINGERPRINT_CACHE", LRUCache(capacity=0))
        await reset_fingerprint_cache()
        import research_agent.rag.indexer as idx_mod
        assert idx_mod._GLOBAL_FINGERPRINT_CACHE.capacity == 50000
        assert len(idx_mod._GLOBAL_FINGERPRINT_CACHE) == 0

    @pytest.mark.asyncio
    async def test_reset_does_not_affect_instance_level_cache(self) -> None:
        """Instance-level _seen_fingerprints are independent of global cache."""
        index = ResearchIndex(collection_name="test_fp_instance")
        item = {"snippet": "Instance level content", "url": "https://test/inst"}
        await index.aadd_finding("t1", "web", item)

        stats_before = index.get_stats()
        await reset_fingerprint_cache()

        # Instance stats should be unchanged
        stats_after = index.get_stats()
        assert stats_after["inserted_points"] == stats_before["inserted_points"]
        index.close()
