import pytest

@pytest.fixture(autouse=True)
def mock_llm_calls(monkeypatch):
    """
    Globally mock litellm.completion and clear out API keys so unit tests do not hang 
    trying to connect to Ollama/OpenRouter or fail due to external embedding shapes.
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIMS_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    def _mock_completion(*args, **kwargs):
        raise ValueError("Litellm disabled during testing")
        
    try:
        import litellm
        monkeypatch.setattr(litellm, "completion", _mock_completion)
    except ImportError:
        pass
