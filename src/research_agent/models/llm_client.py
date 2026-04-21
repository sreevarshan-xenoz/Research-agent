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


def _resolve_model(role: str) -> tuple[str, dict[str, Any], list[dict[str, Any]], str | None]:
    """Resolve the model name, extra kwargs, fallbacks, and specific provider for a given role."""
    from research_agent.config import load_settings
    settings = load_settings()

    if role == "orchestrator" or role == "head":
        model = settings.models.orchestrator_model
        extra: dict[str, Any] = {}
        provider = settings.models.orchestrator_provider
        
        if provider == "ollama":
            extra["api_base"] = settings.ollama.api_base
        elif provider == "openrouter":
            extra["api_key"] = settings.openrouter.api_key or os.getenv("OPENROUTER_API_KEY", "")
        
        return model, extra, [], provider

    # Subagent role
    priority = settings.models.provider_priority
    model_list: list[tuple[str, dict[str, Any], str]] = []

    for provider in priority:
        if provider == "ollama":
            model_list.append((
                f"ollama/{settings.models.subagent_local}",
                {"api_base": settings.ollama.api_base},
                "ollama"
            ))
        elif provider == "nvidia":
            api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIMS_API_KEY")
            if api_key:
                model_list.append((
                    settings.models.subagent_nvidia,
                    {"api_key": api_key},
                    "nvidia"
                ))
        elif provider == "openrouter":
            api_key = settings.openrouter.api_key or os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                model_list.append((
                    settings.models.subagent_cloud,
                    {"api_key": api_key},
                    "openrouter"
                ))

    if not model_list:
        return "gpt-4o-mini", {}, [], None

    primary_model, primary_extra, primary_provider = model_list[0]
    fallbacks = [
        {"model": m, **kwargs} 
        for m, kwargs, p in model_list[1:]
    ]

    return primary_model, primary_extra, fallbacks, primary_provider


def _extract_json(text: str) -> str:
    """Extract JSON from model output, handling markdown code blocks."""
    text = text.strip()
    if not text:
        return text

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()

    for start_char in ["{", "["]:
        idx = text.find(start_char)
        if idx >= 0:
            candidate = text[idx:]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                # Try to find the last occurrence of } or ]
                end_char = "}" if start_char == "{" else "]"
                last_idx = candidate.rfind(end_char)
                if last_idx >= 0:
                    try:
                        return candidate[:last_idx+1]
                    except: pass

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
    model, extra_kwargs, fallbacks, provider = _resolve_model(role)
    if not model:
        return None

    if provider == "nvidia":
        from research_agent.models.nvidia_client import generate_json_with_nvidia
        return generate_json_with_nvidia(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

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
    except Exception as e:
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
    model, extra_kwargs, fallbacks, provider = _resolve_model(role)
    if not model:
        return None

    chunk_handler = on_chunk or _STREAM_CALLBACK.get()

    if provider == "nvidia":
        from research_agent.models.nvidia_client import generate_with_nvidia
        # NVIDIA client handles its own streaming via chunk_handler
        return generate_with_nvidia(
            model=model,
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            on_chunk=chunk_handler
        )

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
                    except Exception:
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
    except Exception as e:
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
    """Generate structured JSON using the model assigned to the given role."""
    model, extra_kwargs, fallbacks, provider = _resolve_model(role)
    if not model:
        return None

    if provider == "nvidia":
        from research_agent.models.nvidia_client import generate_json_with_nvidia
        return generate_json_with_nvidia(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

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
    except Exception as e:
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
    """Generate text using the model assigned to the given role."""
    model, extra_kwargs, fallbacks, provider = _resolve_model(role)
    if not model:
        return None

    chunk_handler = on_chunk or _STREAM_CALLBACK.get()

    if provider == "nvidia":
        from research_agent.models.nvidia_client import generate_with_nvidia
        return generate_with_nvidia(
            model=model,
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            on_chunk=chunk_handler
        )

    try:
        import litellm
        litellm.drop_params = True

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if chunk_handler:
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
                    except Exception:
                        pass

            text = "".join(chunks).strip()
            return text or None
        else:
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
    except Exception as e:
        print(f"LLM Error (generate_text, role={role}): {type(e).__name__}: {str(e)}")
        return None
