"""Unified LLM client for hybrid multi-model architecture.

Routes calls to the appropriate model based on role:
- "head" → local Ollama model (gemma4:e4b) for orchestration tasks
- "subagent" → cloud model (OpenRouter free / NVIDIA NIMs) for heavy generation

Uses litellm as the unified backend for all providers.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator


_STREAM_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar(
    "llm_stream_callback",
    default=None,
)


@contextmanager
def stream_callback(callback: Callable[[str], None] | None) -> Iterator[None]:
    """Context manager to set a streaming callback for subagent generation."""
    token = _STREAM_CALLBACK.set(callback)
    try:
        yield
    finally:
        _STREAM_CALLBACK.reset(token)


def _resolve_model(role: str) -> tuple[str, dict[str, Any]]:
    """Resolve the litellm model string and extra kwargs for a given role.

    Role definitions (from centralized config):
    - "head": Local orchestrator for planning/clarification/critic
    - "subagent": Cloud model for section synthesis/LaTeX composition

    Priority order per role:
    - head: HEAD_MODEL env > default ollama/gemma4:e4b
    - subagent: SUBAGENT_MODEL env > OPENROUTER_API_KEY > NVIDIA_API_KEY > fallback
    """
    if role == "head":
        model = os.getenv("HEAD_MODEL", "").strip()
        if not model:
            # Use config default or fallback
            from research_agent.config import load_settings
            try:
                settings = load_settings()
                model = settings.models.head_model or "ollama/gemma4:e4b"
            except Exception:
                model = "ollama/gemma4:e4b"

        extra: dict[str, Any] = {}
        ollama_base = os.getenv("OLLAMA_API_BASE", "").strip()
        if ollama_base:
            extra["api_base"] = ollama_base
        else:
            # Try default local endpoint
            extra["api_base"] = "http://localhost:11434"

        return model, extra

    # role == "subagent"
    model = os.getenv("SUBAGENT_MODEL", "").strip()
    extra = {}

    if not model:
        # Auto-select from available API keys (priority order)
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if openrouter_key:
            model = "openrouter/openrouter/free"
            extra["api_key"] = openrouter_key
        else:
            nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip() or os.getenv(
                "NVIDIA_NIMS_API_KEY", ""
            ).strip()
            if nvidia_key:
                model = "nvidia_nim/" + (
                    os.getenv("NVIDIA_MODEL", "").strip()
                    or "qwen/qwen3-coder-480b-a35b-instruct"
                )
                extra["api_key"] = nvidia_key
            else:
                # No cloud model available - use deterministic fallback
                return "", {}

    # Inject provider-specific credentials if not already set
    if model.startswith("openrouter/") and "api_key" not in extra:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if key:
            extra["api_key"] = key

    if model.startswith("nvidia_nim/") and "api_key" not in extra:
        key = (
            os.getenv("NVIDIA_API_KEY", "").strip()
            or os.getenv("NVIDIA_NIMS_API_KEY", "").strip()
        )
        if key:
            extra["api_key"] = key

    return model, extra


def _extract_json(text: str) -> str:
    """Extract JSON from model output, handling markdown code blocks."""
    text = text.strip()
    if not text:
        return text

    # Handle ```json ... ``` blocks
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()

    # Handle cases where model prefixes with text before JSON
    for start_char in ["{", "["]:
        idx = text.find(start_char)
        if idx > 0 and idx < 50:
            # Only trim prefix if it's short (likely preamble text)
            candidate = text[idx:]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    return text


async def agenerate_json(
    *,
    role: str = "head",
    prompt: str,
    system_prompt: str = "You are a research assistant that only outputs valid JSON. No markdown, no explanation, just the JSON object.",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict | list | None:
    """Async version of generate_json."""
    model, extra_kwargs = _resolve_model(role)
    if not model:
        return None

    try:
        import litellm

        litellm.drop_params = True

        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **extra_kwargs,
        )

        text = response.choices[0].message.content or ""
        text = _extract_json(text)
        if not text:
            return None

        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


async def agenerate_text(
    *,
    role: str = "subagent",
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: int = 4096,
    on_chunk: Callable[[str], None] | None = None,
) -> str | None:
    """Async version of generate_text with streaming support."""
    model, extra_kwargs = _resolve_model(role)
    if not model:
        return None

    chunk_handler = on_chunk or _STREAM_CALLBACK.get()

    try:
        import litellm

        litellm.drop_params = True

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if chunk_handler:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                **extra_kwargs,
            )

            chunks: list[str] = []
            async for part in response:
                delta = part.choices[0].delta.content or ""
                if delta:
                    chunks.append(delta)
                    try:
                        if asyncio.iscoroutinefunction(chunk_handler):
                            await chunk_handler(delta)
                        else:
                            chunk_handler(delta)
                    except Exception:  # noqa: BLE001
                        pass

            text = "".join(chunks).strip()
            return text or None
        else:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **extra_kwargs,
            )

            text = (response.choices[0].message.content or "").strip()
            return text or None
    except Exception:  # noqa: BLE001
        return None


def generate_json(
    *,
    role: str = "head",
    prompt: str,
    system_prompt: str = "You are a research assistant that only outputs valid JSON. No markdown, no explanation, just the JSON object.",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict | list | None:
    """Generate structured JSON using the model assigned to the given role.

    Args:
        role: "head" for local orchestrator, "subagent" for cloud model.
        prompt: The user prompt to send.
        system_prompt: System instruction for JSON output.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.

    Returns:
        Parsed JSON (dict or list) on success, None on failure.
    """
    model, extra_kwargs = _resolve_model(role)
    if not model:
        return None

    try:
        import litellm

        litellm.drop_params = True

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **extra_kwargs,
        )

        text = response.choices[0].message.content or ""
        text = _extract_json(text)
        if not text:
            return None

        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


def generate_text(
    *,
    role: str = "subagent",
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: int = 4096,
    on_chunk: Callable[[str], None] | None = None,
) -> str | None:
    """Generate text using the model assigned to the given role.

    Supports streaming for real-time UI updates via on_chunk callback.

    Args:
        role: "head" for local orchestrator, "subagent" for cloud model.
        prompt: The user prompt to send.
        system_prompt: Optional system instruction.
        temperature: Sampling temperature.
        top_p: Top-p sampling.
        max_tokens: Maximum tokens to generate.
        on_chunk: Optional callback for streaming chunks.

    Returns:
        Generated text on success, None on failure.
    """
    model, extra_kwargs = _resolve_model(role)
    if not model:
        return None

    chunk_handler = on_chunk or _STREAM_CALLBACK.get()

    try:
        import litellm

        litellm.drop_params = True

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if chunk_handler:
            # Streaming mode
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                **extra_kwargs,
            )

            chunks: list[str] = []
            for part in response:
                delta = part.choices[0].delta.content or ""
                if delta:
                    chunks.append(delta)
                    try:
                        chunk_handler(delta)
                    except Exception:  # noqa: BLE001
                        pass

            text = "".join(chunks).strip()
            return text or None
        else:
            # Non-streaming mode
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **extra_kwargs,
            )

            text = (response.choices[0].message.content or "").strip()
            return text or None
    except Exception:  # noqa: BLE001
        return None
