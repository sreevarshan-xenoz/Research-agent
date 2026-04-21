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


def _resolve_model(role: str) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Resolve the litellm model, extra kwargs, and fallbacks for a given role.

    v2 Implementation:
    - Uses AppSettings for centralized configuration.
    - Implements priority-based fallback (Ollama -> OpenRouter -> Puter).
    """
    from research_agent.config import load_settings
    settings = load_settings()

    if role == "orchestrator" or role == "head":
        model = settings.models.orchestrator_model
        extra: dict[str, Any] = {}
        if settings.models.orchestrator_provider == "ollama":
            extra["api_base"] = settings.ollama.api_base
        elif settings.models.orchestrator_provider == "openrouter":
            extra["api_key"] = settings.openrouter.api_key or os.getenv("OPENROUTER_API_KEY", "")
        
        return model, extra, []

    # Subagent role
    priority = settings.models.provider_priority
    model_list: list[tuple[str, dict[str, Any]]] = []

    for provider in priority:
        if provider == "ollama":
            model_list.append((
                f"ollama/{settings.models.subagent_local}",
                {"api_base": settings.ollama.api_base}
            ))
        elif provider == "openrouter":
            api_key = settings.openrouter.api_key or os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                model_list.append((
                    settings.models.subagent_cloud,
                    {"api_key": api_key}
                ))
        elif provider == "puter":
            model_list.append((
                "openrouter/ai21/jamba-large-1.7",
                {}
            ))

    if not model_list:
        return "gpt-4o-mini", {}, []

    primary_model, primary_extra = model_list[0]
    fallbacks = [
        {"model": m, **kwargs} 
        for m, kwargs in model_list[1:]
    ]

    return primary_model, primary_extra, fallbacks


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
    """Async version of generate_json with v2 fallback support."""
    model, extra_kwargs, fallbacks = _resolve_model(role)
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
            fallbacks=fallbacks,
            **extra_kwargs,
        )

        text = response.choices[0].message.content or ""
        text = _extract_json(text)
        if not text:
            return None

        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        print(f"LLM Error (agenerate_json, role={role}): {type(e).__name__}: {str(e)}")
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
    """Async version of generate_text with streaming and v2 fallback support."""
    model, extra_kwargs, fallbacks = _resolve_model(role)
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
                fallbacks=fallbacks,
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
                fallbacks=fallbacks,
                **extra_kwargs,
            )
            text = (response.choices[0].message.content or "").strip()
            return text or None
    except Exception as e:  # noqa: BLE001
        print(f"LLM Error (role={role}): {type(e).__name__}: {str(e)}")
        return None

        print(f"LLM Error (agenerate_text, role={role}): {type(e).__name__}: {str(e)}")
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

    v2: Includes multi-provider fallback support.
    """
    model, extra_kwargs, fallbacks = _resolve_model(role)
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
            fallbacks=fallbacks,
            **extra_kwargs,
        )

        text = response.choices[0].message.content or ""
        text = _extract_json(text)
        if not text:
            return None

        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        print(f"LLM Error (generate_json, role={role}): {type(e).__name__}: {str(e)}")
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

    Supports streaming and v2 fallback support.
    """
    model, extra_kwargs, fallbacks = _resolve_model(role)
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
                fallbacks=fallbacks,
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
                fallbacks=fallbacks,
                **extra_kwargs,
            )
            text = (response.choices[0].message.content or "").strip()
            return text or None
    except Exception as e:  # noqa: BLE001
        print(f"LLM Error (role={role}): {type(e).__name__}: {str(e)}")
        return None

        print(f"LLM Error (agenerate_text, role={role}): {type(e).__name__}: {str(e)}")
        return None
