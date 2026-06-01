import pytest
from research_agent.tools.huggingface import HuggingFaceDatasetAdapter


def test_huggingface_search():
    adapter = HuggingFaceDatasetAdapter()
    result = adapter.search("text classification", limit=3)
    assert result.provider == "huggingface"
    assert len(result.items) <= 3
