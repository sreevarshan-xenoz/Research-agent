import pytest
from research_agent.tools.open_alex import OpenAlexAdapter

def test_normalize_item_with_inverted_index():
    sample_work = {
        "display_name": "Attention Is All You Need",
        "doi": "https://doi.org/10.48550/arXiv.1706.03762",
        "publication_year": 2017,
        "cited_by_count": 120000,
        "authorships": [
            {"author": {"display_name": "Ashish Vaswani"}},
            {"author": {"display_name": "Noam Shazeer"}}
        ],
        "abstract_inverted_index": {
            "The": [0],
            "dominant": [1],
            "sequence": [2, 5],
            "transduction": [3],
            "models": [4]
        },
        "id": "https://openalex.org/W123456789"
    }
    
    adapter = OpenAlexAdapter()
    normalized = adapter._normalize_item(sample_work)
    
    assert normalized["title"] == "Attention Is All You Need"
    assert normalized["year"] == 2017
    assert normalized["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert normalized["snippet"] == "The dominant sequence transduction models sequence"
    assert normalized["url"] == "https://doi.org/10.48550/arXiv.1706.03762"
    assert normalized["provider"] == "openalex"

def test_normalize_item_minimal():
    sample_work = {
        "display_name": "Minimal Paper",
        "id": "W1"
    }
    adapter = OpenAlexAdapter()
    normalized = adapter._normalize_item(sample_work)
    assert normalized["title"] == "Minimal Paper"
    assert normalized["snippet"] == ""
    assert normalized["authors"] == []
