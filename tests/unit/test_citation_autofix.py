from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from research_agent.orchestration.nodes.citation_verifier import _autofix_citations
from research_agent.tools.base import ToolResult

@pytest.mark.asyncio
async def test_autofix_citations_repairs_missing_metadata() -> None:
    # Arrange
    citations = [
        {
            "key": "t1_fake_1",
            "title": "Incomplete Title",
            "url": "",
            "year": "2026",
            "author": "Unknown",
        }
    ]
    
    mock_item = {
        "title": "Complete Title from OpenAlex",
        "authors": ["Author B"],
        "url": "https://doi.org/10.1234/5678",
        "year": "2025"
    }
    
    mock_result = ToolResult(
        provider="openalex",
        items=[mock_item]
    )
    
    # Act
    # We need to patch the OpenAlexAdapter.search method
    with patch("research_agent.orchestration.nodes.citation_verifier.OpenAlexAdapter.search") as mock_search:
        mock_search.return_value = mock_result
        
        fixed_citations, repaired_count = await _autofix_citations(citations)
        
    # Assert
    assert repaired_count == 1
    assert fixed_citations[0]["title"] == "Complete Title from OpenAlex"
    assert fixed_citations[0]["author"] == "Author B"
    assert fixed_citations[0]["url"] == "https://doi.org/10.1234/5678"
    assert fixed_citations[0]["year"] == "2025"

@pytest.mark.asyncio
async def test_autofix_citations_skips_complete_records() -> None:
    # Arrange
    citations = [
        {
            "key": "t1_fake_1",
            "title": "A Very Complete Title",
            "url": "https://example.com/complete",
            "year": "2026",
            "author": "Author A",
        }
    ]
    
    # Act
    with patch("research_agent.orchestration.nodes.citation_verifier.OpenAlexAdapter.search") as mock_search:
        fixed_citations, repaired_count = await _autofix_citations(citations)
        
    # Assert
    assert repaired_count == 0
    assert fixed_citations == citations
    mock_search.assert_not_called()
