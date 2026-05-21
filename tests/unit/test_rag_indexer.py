import pytest
from research_agent.rag.indexer import ResearchIndex


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
