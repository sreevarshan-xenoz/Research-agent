from __future__ import annotations

import pytest
from research_agent.tools.pubmed import PubMedAdapter

def test_pubmed_normalize_item():
    adapter = PubMedAdapter()
    uid = "12345"
    row = {
        "title": "A Great Study",
        "authors": [{"name": "Dr. Smith"}, {"name": "Prof. Jones"}],
        "pubdate": "2024 May 01",
        "fulljournalname": "Nature Medicine",
        "articleids": [
            {"idtype": "doi", "value": "10.1234/nature12345"},
            {"idtype": "pubmed", "value": "12345"}
        ]
    }
    
    item = adapter._normalize_item(uid, row)
    
    assert item["title"] == "A Great Study"
    assert item["url"] == "https://doi.org/10.1234/nature12345"
    assert item["paper_id"] == "12345"
    assert item["year"] == "2024"
    assert "Dr. Smith" in item["authors"]
    assert item["provider"] == "pubmed"

@pytest.mark.asyncio
async def test_pubmed_search_integration():
    # This test actually hits the NCBI API (live)
    adapter = PubMedAdapter()
    result = await adapter.asearch("CRISPR gene editing", limit=2)
    
    assert result.provider == "pubmed"
    # Basic check to see if we got results (NCBI usually returns something for CRISPR)
    if not result.warnings:
        assert len(result.items) > 0
        assert "title" in result.items[0]
        assert "authors" in result.items[0]
