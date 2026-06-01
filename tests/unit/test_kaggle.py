import pytest
from research_agent.tools.kaggle import KaggleDatasetAdapter


def test_kaggle_search():
    adapter = KaggleDatasetAdapter()
    result = adapter.search("nlp", limit=3)
    assert result.provider == "kaggle"
