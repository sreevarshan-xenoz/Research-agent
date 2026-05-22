import pytest

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
