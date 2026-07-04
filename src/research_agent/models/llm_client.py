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
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator

from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from research_agent.tools.rate_limiter import get_limiter


logger = logging.getLogger(__name__)


# Module-level rate limiters for cloud LLM providers
_openrouter_limiter = get_limiter("openrouter")
_nvidia_llm_limiter = get_limiter("nvidia_llm")
_openai_limiter = get_limiter("openai_llm")
_anthropic_limiter = get_limiter("anthropic_llm")
_gemini_limiter = get_limiter("gemini_llm")
_groq_limiter = get_limiter("groq_llm")


# ---------------------------------------------------------------------------
# Cost and latency tracking context
# ---------------------------------------------------------------------------

_STREAM_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar(
    "llm_stream_callback",
    default=None,
)

_CURRENT_RUN_ID: ContextVar[str | None] = ContextVar(
    "llm_run_id",
    default=None,
)

_CURRENT_TASK_TYPE: ContextVar[str | None] = ContextVar(
    "llm_task_type",
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


@contextmanager
def with_run_cost_tracking(run_id: str, task_type: str = "subagent") -> Iterator[None]:
    """Context manager that enables cost and latency tracking on subsequent LLM calls.

    All generate_text / generate_json / agenerate_text / agenerate_json calls
    made within this context will automatically record their token usage, cost,
    and latency against the specified run_id.

    Usage:
        with with_run_cost_tracking("run-123", task_type="write"):
            result = generate_text(role="subagent", prompt="...")

        # also works in async contexts:
        async with with_run_cost_tracking("run-123"):
            result = await agenerate_text(role="subagent", prompt="...")
    """
    token_run = _CURRENT_RUN_ID.set(run_id)
    token_task = _CURRENT_TASK_TYPE.set(task_type)
    try:
        yield
    finally:
        _CURRENT_RUN_ID.reset(token_run)
        _CURRENT_TASK_TYPE.reset(token_task)


def _resolve_api_key(key_val: Any) -> str:
    """Extract a plain string API key from a SecretStr, env var, or raw string."""
    from pydantic import SecretStr
    if isinstance(key_val, SecretStr):
        return key_val.get_secret_value()
    return str(key_val or "")


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
            key = _resolve_api_key(settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
            if key:
                extra["api_key"] = key
        elif provider == "openai":
            key = _resolve_api_key(settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
            if key:
                extra["api_key"] = key
            if settings.openai.api_base or os.getenv("OPENAI_API_BASE"):
                extra["api_base"] = settings.openai.api_base or os.getenv("OPENAI_API_BASE")
            if settings.openai.organization or os.getenv("OPENAI_ORGANIZATION"):
                extra["organization"] = settings.openai.organization or os.getenv("OPENAI_ORGANIZATION")
        elif provider == "anthropic":
            key = _resolve_api_key(settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
            if key:
                extra["api_key"] = key
            if settings.anthropic.api_base:
                extra["api_base"] = settings.anthropic.api_base
        elif provider == "gemini":
            key = _resolve_api_key(settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
            if key:
                extra["api_key"] = key
            if settings.gemini.api_base:
                extra["api_base"] = settings.gemini.api_base
        elif provider == "groq":
            key = _resolve_api_key(settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
            if key:
                extra["api_key"] = key
            if settings.groq.api_base:
                extra["api_base"] = settings.groq.api_base

        return model, extra, [], provider

    # Subagent role
    priority = settings.models.provider_priority
    model_list: list[tuple[str, dict[str, Any], str]] = []

    for prov in priority:
        if prov == "vllm":
            api_key = _resolve_api_key(settings.vllm.api_key) or os.getenv("VLLM_API_KEY", "")
            model_list.append((
                f"openai/{settings.models.subagent_vllm}",
                {"api_base": settings.vllm.api_base, "api_key": api_key},
                "vllm"
            ))
        elif prov == "ollama":
            model_list.append((
                f"ollama/{settings.models.subagent_local}",
                {"api_base": settings.ollama.api_base},
                "ollama"
            ))
        elif prov == "nvidia":
            api_key = os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")
            if api_key:
                model_list.append((
                    settings.models.subagent_nvidia,
                    {"api_key": api_key},
                    "nvidia"
                ))
        elif prov == "openrouter":
            api_key = _resolve_api_key(settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                model_list.append((
                    settings.models.subagent_cloud,
                    {"api_key": api_key},
                    "openrouter"
                ))
        elif prov == "openai":
            api_key = _resolve_api_key(settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
            if api_key:
                openai_extra: dict[str, Any] = {"api_key": api_key}
                if settings.openai.api_base or os.getenv("OPENAI_API_BASE"):
                    openai_extra["api_base"] = settings.openai.api_base or os.getenv("OPENAI_API_BASE")
                if settings.openai.organization or os.getenv("OPENAI_ORGANIZATION"):
                    openai_extra["organization"] = settings.openai.organization or os.getenv("OPENAI_ORGANIZATION")
                model_list.append((
                    settings.models.subagent_openai,
                    openai_extra,
                    "openai"
                ))
        elif prov == "anthropic":
            api_key = _resolve_api_key(settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
            if api_key:
                anthropic_extra: dict[str, Any] = {"api_key": api_key}
                if settings.anthropic.api_base:
                    anthropic_extra["api_base"] = settings.anthropic.api_base
                model_list.append((
                    settings.models.subagent_anthropic,
                    anthropic_extra,
                    "anthropic"
                ))
        elif prov == "gemini":
            api_key = _resolve_api_key(settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
            if api_key:
                gemini_extra: dict[str, Any] = {"api_key": api_key}
                if settings.gemini.api_base:
                    gemini_extra["api_base"] = settings.gemini.api_base
                model_list.append((
                    settings.models.subagent_gemini,
                    gemini_extra,
                    "gemini"
                ))
        elif prov == "groq":
            api_key = _resolve_api_key(settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
            if api_key:
                groq_extra: dict[str, Any] = {"api_key": api_key}
                if settings.groq.api_base:
                    groq_extra["api_base"] = settings.groq.api_base
                model_list.append((
                    settings.models.subagent_groq,
                    groq_extra,
                    "groq"
                ))

    if not model_list:
        return "gpt-4o-mini", {}, [], None

    primary_model, primary_extra, primary_provider = model_list[0]
    fallbacks = [
        {"model": m, **kwargs} 
        for m, kwargs, p in model_list[1:]
    ]

    return primary_model, primary_extra, fallbacks, primary_provider


def resolve_model_for_task(
    task_type: str,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], str | None]:
    """Resolve model configuration for a specific task type using the model_router.

    Task types: plan, write, critique, code, embed, search, evaluate
    Falls back to default_model or _resolve_model(role="subagent") if no
    task-specific mapping exists.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    router = settings.model_router
    if not router.enabled:
        return _resolve_model("subagent")

    task_config = router.tasks.get(task_type)
    if task_config is None:
        if router.default_model:
            # Resolve API key for the default provider
            default_extra: dict[str, Any] = {}
            default_prov = router.default_provider
            if default_prov == "ollama":
                default_extra["api_base"] = settings.ollama.api_base
            elif default_prov == "openrouter":
                key = _resolve_api_key(settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
            elif default_prov == "nvidia":
                key = os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
            elif default_prov == "openai":
                key = _resolve_api_key(settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
                if settings.openai.api_base or os.getenv("OPENAI_API_BASE"):
                    default_extra["api_base"] = settings.openai.api_base or os.getenv("OPENAI_API_BASE")
            elif default_prov == "anthropic":
                key = _resolve_api_key(settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
            elif default_prov == "gemini":
                key = _resolve_api_key(settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
                if settings.gemini.api_base:
                    default_extra["api_base"] = settings.gemini.api_base
            elif default_prov == "groq":
                key = _resolve_api_key(settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
                if key:
                    default_extra["api_key"] = key
                if settings.groq.api_base:
                    default_extra["api_base"] = settings.groq.api_base
            elif default_prov == "vllm":
                key = _resolve_api_key(settings.vllm.api_key) or os.getenv("VLLM_API_KEY", "")
                default_extra["api_base"] = settings.vllm.api_base
                if key:
                    default_extra["api_key"] = key
            return router.default_model, default_extra, [], default_prov
        return _resolve_model("subagent")

    provider = task_config.provider
    model = task_config.model
    extra: dict[str, Any] = {}

    if task_config.temperature is not None:
        extra["temperature"] = task_config.temperature
    if task_config.max_tokens is not None:
        extra["max_tokens"] = task_config.max_tokens

    # Resolve API keys and base URLs based on provider
    if provider == "ollama":
        extra["api_base"] = settings.ollama.api_base
    elif provider == "openrouter":
        key = _resolve_api_key(settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
        if key:
            extra["api_key"] = key
    elif provider == "nvidia":
        key = os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")
        if key:
            extra["api_key"] = key
    elif provider == "openai":
        key = _resolve_api_key(settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
        if key:
            extra["api_key"] = key
        if settings.openai.api_base or os.getenv("OPENAI_API_BASE"):
            extra["api_base"] = settings.openai.api_base or os.getenv("OPENAI_API_BASE")
    elif provider == "anthropic":
        key = _resolve_api_key(settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            extra["api_key"] = key
    elif provider == "gemini":
        key = _resolve_api_key(settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
        if key:
            extra["api_key"] = key
        if settings.gemini.api_base:
            extra["api_base"] = settings.gemini.api_base
    elif provider == "groq":
        key = _resolve_api_key(settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
        if key:
            extra["api_key"] = key
        if settings.groq.api_base:
            extra["api_base"] = settings.groq.api_base
    elif provider == "vllm":
        key = _resolve_api_key(settings.vllm.api_key) or os.getenv("VLLM_API_KEY", "")
        extra["api_base"] = settings.vllm.api_base
        if key:
            extra["api_key"] = key

    # Build fallback chain from remaining priority providers
    fallbacks = []
    priority = settings.models.provider_priority
    for prov in priority:
        if prov == provider:
            continue  # Skip primary provider
        fallback_extra: dict[str, Any] = {}
        fallback_model: str = ""

        if prov == "ollama":
            fallback_extra["api_base"] = settings.ollama.api_base
            fallback_model = f"ollama/{settings.models.subagent_local}"
        elif prov == "openrouter":
            fk = _resolve_api_key(settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_cloud
        elif prov == "nvidia":
            fk = os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_nvidia
        elif prov == "openai":
            fk = _resolve_api_key(settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_openai
        elif prov == "anthropic":
            fk = _resolve_api_key(settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_anthropic
        elif prov == "gemini":
            fk = _resolve_api_key(settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_gemini
        elif prov == "groq":
            fk = _resolve_api_key(settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
            if not fk:
                continue
            fallback_extra["api_key"] = fk
            fallback_model = settings.models.subagent_groq
        elif prov == "vllm":
            fk = _resolve_api_key(settings.vllm.api_key) or os.getenv("VLLM_API_KEY", "")
            fallback_extra["api_base"] = settings.vllm.api_base
            if fk:
                fallback_extra["api_key"] = fk
            fallback_model = f"openai/{settings.models.subagent_vllm}"
        else:
            continue

        fallbacks.append({"model": fallback_model, **fallback_extra})
        if len(fallbacks) >= 3:
            break  # Limit to 3 fallbacks

    return model, extra, fallbacks, provider


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
                    except Exception:
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
    model, extra_kwargs, fallbacks, provider = _resolve_model(role)
    if not model:
        return None

    task_type = _CURRENT_TASK_TYPE.get() or "agenerate_json"

    if not provider:
        provider = "unknown"

    if provider == "nvidia":
        _nvidia_llm_limiter.sync_acquire()
        try:
            from research_agent.models.nvidia_client import generate_json_with_nvidia
            from research_agent.models.latency_tracker import track_latency
            async with track_latency(provider, model):
                result = generate_json_with_nvidia(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            if result is not None:
                _nvidia_llm_limiter.record_success()
                await _record_cost_from_text_async(
                    json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                    model, provider, task_type,
                )
            else:
                _nvidia_llm_limiter.record_error()
            return result
        except Exception:
            _nvidia_llm_limiter.record_error()
            raise

    try:
        import litellm
        litellm.drop_params = True

        # Acquire rate limiter for non-local providers
        if provider == "openrouter":
            await _openrouter_limiter.async_acquire()
        elif provider == "openai":
            await _openai_limiter.async_acquire()
        elif provider == "anthropic":
            await _anthropic_limiter.async_acquire()
        elif provider == "gemini":
            await _gemini_limiter.async_acquire()
        elif provider == "groq":
            await _groq_limiter.async_acquire()

        from research_agent.models.latency_tracker import track_latency

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                async with track_latency(provider, model):
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

        
        # response is guaranteed to exist here — retry loop raises on exhaustion
        text = response.choices[0].message.content or ""  # type: ignore[union-attr]
        text = _extract_json(text)
        if not text:
            return None

        result = json.loads(text)
        await _record_cost_from_response_async(response, model, provider, task_type)  # type: ignore[arg-type]
        return result
    except Exception as e:
        from research_agent.observability.metrics import count_llm_request
        count_llm_request(provider or "unknown", status="error")
        logger.warning("LLM Error (agenerate_json, role=%s): %s: %s", role, type(e).__name__, e)
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
    task_type = _CURRENT_TASK_TYPE.get() or role

    if not provider:
        provider = "unknown"

    if provider == "nvidia":
        _nvidia_llm_limiter.sync_acquire()
        try:
            from research_agent.models.nvidia_client import generate_with_nvidia
            from research_agent.models.latency_tracker import track_latency
            async with track_latency(provider, model):
                result = generate_with_nvidia(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    on_chunk=chunk_handler
                )
            if result is not None:
                _nvidia_llm_limiter.record_success()
                await _record_cost_from_text_async(result, model, provider, task_type)
            else:
                _nvidia_llm_limiter.record_error()
            return result
        except Exception:
            _nvidia_llm_limiter.record_error()
            raise

    try:
        import litellm
        litellm.drop_params = True

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Acquire rate limiter for non-local providers
        if provider == "openrouter":
            await _openrouter_limiter.async_acquire()
        elif provider == "openai":
            await _openai_limiter.async_acquire()
        elif provider == "anthropic":
            await _anthropic_limiter.async_acquire()
        elif provider == "gemini":
            await _gemini_limiter.async_acquire()
        elif provider == "groq":
            await _groq_limiter.async_acquire()

        from research_agent.models.latency_tracker import track_latency

        if chunk_handler:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
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
            async with track_latency(provider, model):
                async for part in response:  # type: ignore[union-attr]
                    delta = part.choices[0].delta.content or ""
                    if delta:
                        chunks.append(delta)
                        try:
                            if asyncio.iscoroutinefunction(chunk_handler):
                                await chunk_handler(delta)
                            else:
                                chunk_handler(delta)
                        except Exception as chunk_err:
                            logger.warning("Stream chunk callback (async) failed: %s", chunk_err)

            text = "".join(chunks).strip()
            result = text or None
            await _record_cost_from_text_async(result, model, provider, task_type)
            return result
        else:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    async with track_latency(provider, model):
                        response = await litellm.acompletion(  # type: ignore[assignment]
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                            fallbacks=fallbacks,
                            **extra_kwargs,
                        )
            text = (response.choices[0].message.content or "").strip()  # type: ignore[union-attr]
            result = text or None
            await _record_cost_from_response_async(response, model, provider, task_type)  # type: ignore[arg-type]
            return result
    except Exception as e:
        from research_agent.observability.metrics import count_llm_request
        count_llm_request(provider or "unknown", status="error")
        logger.warning("LLM Error (agenerate_text, role=%s): %s: %s", role, type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# Token estimation helper
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Roughly estimate token count from text length.

    For English text, a reasonable heuristic is ~4 characters per token.
    This is used when the LLM provider doesn't return usage stats
    (e.g. in streaming mode).
    """
    return max(1, len(text) // 4)


def _record_cost_from_response(
    response: Any,
    model: str,
    provider: str,
    task_type: str,
) -> None:
    """Record cost from a litellm response object, if a run context is active.

    This is the sync variant, called from generate_json/generate_text.
    """
    run_id = _CURRENT_RUN_ID.get()
    if run_id is None:
        return

    try:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
    except Exception:
        input_tokens = 0
        output_tokens = 0

    if input_tokens == 0 and output_tokens == 0:
        try:
            text = response.choices[0].message.content or ""
            output_tokens = _estimate_tokens(text)
        except Exception:
            output_tokens = 0

    from research_agent.models.cost_tracker import get_cost_tracker_sync
    from research_agent.observability.metrics import record_llm_cost, count_llm_request
    try:
        tracker = get_cost_tracker_sync(run_id)
        tracker.record_sync(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        # Estimate per-request cost from token counts
        estimated_cost = (input_tokens * 0.000002 + output_tokens * 0.000005)
        record_llm_cost(provider, model, estimated_cost)
        count_llm_request(provider, status="success")
    except Exception as exc:
        logger.debug("Failed to record cost: %s", exc)


async def _record_cost_from_response_async(
    response: Any,
    model: str,
    provider: str,
    task_type: str,
) -> None:
    """Async version of _record_cost_from_response."""
    run_id = _CURRENT_RUN_ID.get()
    if run_id is None:
        return

    try:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
    except Exception:
        input_tokens = 0
        output_tokens = 0

    if input_tokens == 0 and output_tokens == 0:
        try:
            text = response.choices[0].message.content or ""
            output_tokens = _estimate_tokens(text)
        except Exception:
            output_tokens = 0

    from research_agent.models.cost_tracker import get_cost_tracker
    try:
        tracker = await get_cost_tracker(run_id)
        await tracker.record(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        from research_agent.observability.metrics import record_llm_cost, count_llm_request
        try:
            estimated_cost = (input_tokens * 0.000002 + output_tokens * 0.000005)
            record_llm_cost(provider, model, estimated_cost)
            count_llm_request(provider, status="success")
        except Exception:
            pass
    except Exception as exc:
        logger.debug("Failed to record cost (async): %s", exc)


def _record_cost_from_text(
    text: str | None,
    model: str,
    provider: str,
    task_type: str,
) -> None:
    """Record estimated cost from output text (sync variant, used for streaming)."""
    run_id = _CURRENT_RUN_ID.get()
    if run_id is None:
        return

    output_tokens = _estimate_tokens(text or "")
    from research_agent.models.cost_tracker import get_cost_tracker_sync
    from research_agent.observability.metrics import record_llm_cost, count_llm_request
    try:
        tracker = get_cost_tracker_sync(run_id)
        tracker.record_sync(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=0,
            output_tokens=output_tokens,
        )
        # Estimate per-request cost from output tokens only (streaming)
        estimated_cost = output_tokens * 0.000005
        record_llm_cost(provider, model, estimated_cost)
        count_llm_request(provider, status="success")
    except Exception as exc:
        logger.debug("Failed to record cost from text: %s", exc)


async def _record_cost_from_text_async(
    text: str | None,
    model: str,
    provider: str,
    task_type: str,
) -> None:
    """Async version of _record_cost_from_text."""
    run_id = _CURRENT_RUN_ID.get()
    if run_id is None:
        return

    output_tokens = _estimate_tokens(text or "")
    from research_agent.models.cost_tracker import get_cost_tracker
    try:
        tracker = await get_cost_tracker(run_id)
        await tracker.record(
            model=model,
            provider=provider,
            task_type=task_type,
            input_tokens=0,
            output_tokens=output_tokens,
        )
        from research_agent.observability.metrics import record_llm_cost, count_llm_request
        # Estimate per-request cost from output tokens only (streaming)
        estimated_cost = output_tokens * 0.000005
        record_llm_cost(provider, model, estimated_cost)
        count_llm_request(provider, status="success")
    except Exception as exc:
        logger.debug("Failed to record cost from text (async): %s", exc)


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

    task_type = _CURRENT_TASK_TYPE.get() or "generate_json"

    if not provider:
        provider = "unknown"

    if provider == "nvidia":
        _nvidia_llm_limiter.sync_acquire()
        try:
            from research_agent.models.nvidia_client import generate_json_with_nvidia
            from research_agent.models.latency_tracker import track_latency_sync
            with track_latency_sync(provider, model):
                result = generate_json_with_nvidia(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            if result is not None:
                _nvidia_llm_limiter.record_success()
                _record_cost_from_text(json.dumps(result) if isinstance(result, (dict, list)) else str(result), model, provider, task_type)
            else:
                _nvidia_llm_limiter.record_error()
            return result
        except Exception:
            _nvidia_llm_limiter.record_error()
            raise

    try:
        import litellm
        litellm.drop_params = True

        # Acquire rate limiter for non-local providers
        if provider == "openrouter":
            _openrouter_limiter.sync_acquire()
        elif provider == "openai":
            _openai_limiter.sync_acquire()
        elif provider == "anthropic":
            _anthropic_limiter.sync_acquire()
        elif provider == "gemini":
            _gemini_limiter.sync_acquire()
        elif provider == "groq":
            _groq_limiter.sync_acquire()

        from research_agent.models.latency_tracker import track_latency_sync

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                with track_latency_sync(provider, model):
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

        
        # response is guaranteed to exist here — retry loop raises on exhaustion
        text = response.choices[0].message.content or ""  # type: ignore[union-attr]
        text = _extract_json(text)
        if not text:
            return None

        result = json.loads(text)
        _record_cost_from_response(response, model, provider, task_type)  # type: ignore[arg-type]
        return result
    except Exception as e:
        from research_agent.observability.metrics import count_llm_request
        count_llm_request(provider or "unknown", status="error")
        logger.warning("LLM Error (generate_json, role=%s): %s: %s", role, type(e).__name__, e)
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
    task_type = _CURRENT_TASK_TYPE.get() or role

    if not provider:
        provider = "unknown"

    if provider == "nvidia":
        _nvidia_llm_limiter.sync_acquire()
        try:
            from research_agent.models.nvidia_client import generate_with_nvidia
            from research_agent.models.latency_tracker import track_latency_sync
            with track_latency_sync(provider, model):
                result = generate_with_nvidia(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    on_chunk=chunk_handler
                )
            if result is not None:
                _nvidia_llm_limiter.record_success()
                _record_cost_from_text(result, model, provider, task_type)
            else:
                _nvidia_llm_limiter.record_error()
            return result
        except Exception:
            _nvidia_llm_limiter.record_error()
            raise

    try:
        import litellm
        litellm.drop_params = True

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Acquire rate limiter for non-local providers
        if provider == "openrouter":
            _openrouter_limiter.sync_acquire()
        elif provider == "openai":
            _openai_limiter.sync_acquire()
        elif provider == "anthropic":
            _anthropic_limiter.sync_acquire()
        elif provider == "gemini":
            _gemini_limiter.sync_acquire()
        elif provider == "groq":
            _groq_limiter.sync_acquire()

        from research_agent.models.latency_tracker import track_latency_sync

        if chunk_handler:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
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
            with track_latency_sync(provider, model):
                for part in response:  # type: ignore[union-attr]
                    delta = part.choices[0].delta.content or ""
                    if delta:
                        chunks.append(delta)
                        try:
                            chunk_handler(delta)
                        except Exception as chunk_err:
                            logger.warning("Stream chunk callback (sync) failed: %s", chunk_err)

            text = "".join(chunks).strip()
            result = text or None
            _record_cost_from_text(result, model, provider, task_type)
            return result
        else:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    with track_latency_sync(provider, model):
                        response = litellm.completion(  # type: ignore[assignment]
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                            fallbacks=fallbacks,
                            **extra_kwargs,
                        )
            text = (response.choices[0].message.content or "").strip()  # type: ignore[union-attr]
            result = text or None
            _record_cost_from_response(response, model, provider, task_type)  # type: ignore[arg-type]
            return result
    except Exception as e:
        from research_agent.observability.metrics import count_llm_request
        count_llm_request(provider or "unknown", status="error")
        logger.warning("LLM Error (generate_text, role=%s): %s: %s", role, type(e).__name__, e)
        return None
