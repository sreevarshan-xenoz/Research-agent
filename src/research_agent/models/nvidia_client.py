from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import os
from typing import Callable, Iterator


_NVIDIA_STREAM_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar(
    "nvidia_stream_callback",
    default=None,
)


def _normalize_model_name(model_name: str) -> str:
    prefix = "nvidia_nim/"
    if model_name.startswith(prefix):
        return model_name[len(prefix) :]
    return model_name


@contextmanager
def nvidia_stream_callback(callback: Callable[[str], None] | None) -> Iterator[None]:
    token = _NVIDIA_STREAM_CALLBACK.set(callback)
    try:
        yield
    finally:
        _NVIDIA_STREAM_CALLBACK.reset(token)


def generate_with_nvidia(
    *,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: int = 4096,
    on_chunk: Callable[[str], None] | None = None,
) -> str | None:
    """Generate content using NVIDIA ChatNVIDIA streaming API.

    Returns None when configuration/dependency is missing or generation fails.
    """
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIMS_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
    except Exception:  # noqa: BLE001
        return None

    normalized_model = _normalize_model_name(model)
    stream_handler = on_chunk or _NVIDIA_STREAM_CALLBACK.get()

    try:
        client = ChatNVIDIA(
            model=normalized_model,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        chunks: list[str] = []
        for chunk in client.stream([{"role": "user", "content": prompt}]):
            content = getattr(chunk, "content", "")
            if content:
                chunks.append(content)
                if stream_handler is not None:
                    try:
                        stream_handler(content)
                    except Exception:  # noqa: BLE001
                        # Ignore UI callback failures and continue generation.
                        pass

        text = "".join(chunks).strip()
        return text or None
    except Exception:  # noqa: BLE001
        return None


def generate_json_with_nvidia(
    *,
    model: str,
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict | list | None:
    """Generate structured JSON content using NVIDIA ChatNVIDIA API."""
    import json

    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIMS_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
    except Exception:  # noqa: BLE001
        return None

    normalized_model = _normalize_model_name(model)

    try:
        client = ChatNVIDIA(
            model=normalized_model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = client.invoke(
            [
                {
                    "role": "system",
                    "content": "You are a research assistant that only outputs valid JSON.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        text = str(getattr(response, "content", "")).strip()
        if not text:
            return None

        # Basic JSON extraction in case of markdown blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None
