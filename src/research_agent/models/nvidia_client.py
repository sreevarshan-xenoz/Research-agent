from __future__ import annotations

import os


def _normalize_model_name(model_name: str) -> str:
    prefix = "nvidia_nim/"
    if model_name.startswith(prefix):
        return model_name[len(prefix) :]
    return model_name


def generate_with_nvidia(
    *,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: int = 4096,
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

        text = "".join(chunks).strip()
        return text or None
    except Exception:  # noqa: BLE001
        return None
