from __future__ import annotations

import types

from research_agent.models.nvidia_client import _normalize_model_name, generate_with_nvidia, nvidia_stream_callback


def test_normalize_model_name_supports_prefixed_value() -> None:
    assert _normalize_model_name("nvidia_nim/qwen/qwen3-coder-480b-a35b-instruct") == (
        "qwen/qwen3-coder-480b-a35b-instruct"
    )


def test_generate_with_nvidia_returns_none_when_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIMS_API_KEY", raising=False)

    value = generate_with_nvidia(
        model="qwen/qwen3-coder-480b-a35b-instruct",
        prompt="Hello",
    )
    assert value is None


def test_generate_with_nvidia_uses_streaming_client(monkeypatch) -> None:
    class FakeChunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeChatNVIDIA:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

        def stream(self, messages):  # noqa: ANN001, ANN201
            assert messages[0]["role"] == "user"
            yield FakeChunk("hello ")
            yield FakeChunk("world")

    fake_module = types.SimpleNamespace(ChatNVIDIA=FakeChatNVIDIA)
    monkeypatch.setitem(__import__("sys").modules, "langchain_nvidia_ai_endpoints", fake_module)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    value = generate_with_nvidia(
        model="qwen/qwen3-coder-480b-a35b-instruct",
        prompt="Generate",
    )
    assert value == "hello world"


def test_generate_with_nvidia_emits_chunk_callback(monkeypatch) -> None:
    class FakeChunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeChatNVIDIA:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

        def stream(self, messages):  # noqa: ANN001, ANN201
            assert messages[0]["role"] == "user"
            yield FakeChunk("a")
            yield FakeChunk("b")

    fake_module = types.SimpleNamespace(ChatNVIDIA=FakeChatNVIDIA)
    monkeypatch.setitem(__import__("sys").modules, "langchain_nvidia_ai_endpoints", fake_module)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    captured: list[str] = []
    with nvidia_stream_callback(captured.append):
        value = generate_with_nvidia(
            model="qwen/qwen3-coder-480b-a35b-instruct",
            prompt="Generate",
        )

    assert value == "ab"
    assert captured == ["a", "b"]
