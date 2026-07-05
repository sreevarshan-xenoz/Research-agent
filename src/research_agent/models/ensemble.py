"""Multi-Model Ensemble Voting for critical research tasks.

Runs N models from different providers in parallel on the same prompt and
aggregates their responses using configurable voting strategies. Designed
for high-stakes decision points: critic scoring, planner decomposition,
composer synthesis, bias detection, and hallucination guard.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from research_agent.models.llm_client import _extract_json
from research_agent.tools.rate_limiter import get_limiter

logger = logging.getLogger(__name__)


# Module-level rate limiters for cloud LLM providers
_openrouter_limiter = get_limiter("openrouter")
_openai_limiter = get_limiter("openai_llm")
_anthropic_limiter = get_limiter("anthropic_llm")
_gemini_limiter = get_limiter("gemini_llm")
_groq_limiter = get_limiter("groq_llm")


# ---------------------------------------------------------------------------
# Voting Strategies
# ---------------------------------------------------------------------------


class VotingStrategy(str, Enum):
    """Strategy for aggregating multi-model responses."""

    MAJORITY = "majority"           # Most common discrete answer wins
    WEIGHTED = "weighted"           # Weighted average of numeric scores
    RANK_BORDA = "rank_borda"       # Borda count for ranked choices
    CONFIDENCE = "confidence"       # Weight by per-model confidence score
    CONSENSUS = "consensus"         # Require agreement threshold (default 0.6)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ModelVote:
    """A single model's response in an ensemble call."""
    model_name: str
    provider: str
    raw_text: str
    parsed_json: dict[str, Any] | list[Any] | None = None
    confidence: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class EnsembleResult:
    """Aggregated result from an ensemble voting round."""
    task_type: str
    strategy: VotingStrategy
    votes: list[ModelVote] = field(default_factory=list)
    num_models: int = 0
    num_success: int = 0
    num_failures: int = 0
    aggregated_text: str = ""
    aggregated_json: dict[str, Any] | list[Any] | None = None
    consensus_score: float = 0.0
    disagreement_detected: bool = False
    disagreement_detail: str = ""
    total_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Prompt configuration per task type
# ---------------------------------------------------------------------------

_STRATEGY_MAP: dict[str, VotingStrategy] = {
    "majority": VotingStrategy.MAJORITY,
    "weighted": VotingStrategy.WEIGHTED,
    "rank_borda": VotingStrategy.RANK_BORDA,
    "confidence": VotingStrategy.CONFIDENCE,
    "consensus": VotingStrategy.CONSENSUS,
}


def get_ensemble_config(task_type: str) -> tuple[VotingStrategy, int, int, float]:
    """Get ensemble configuration for a task type from settings or defaults."""
    from research_agent.config import load_settings
    try:
        settings = load_settings()
        if settings.ensemble.enabled and settings.ensemble.task_overrides:
            override = settings.ensemble.task_overrides.get(task_type)
            if override:
                strat = _STRATEGY_MAP.get(
                    str(override.get("strategy", "majority")),
                    VotingStrategy.MAJORITY,
                )
                n_models = int(override.get("num_models", 3))
                timeout = float(override.get("timeout_s", 30.0))
                min_ok = max(1, int(n_models * settings.ensemble.min_success_ratio))
                return (strat, n_models, min_ok, timeout)
    except Exception:
        pass

    # Fallback defaults
    return (VotingStrategy.MAJORITY, 2, 1, 30.0)


# ---------------------------------------------------------------------------
# Resolver: build list of distinct model+provider combos
# ---------------------------------------------------------------------------


def _resolve_ensemble_models(num_models: int) -> list[dict[str, Any]]:
    """Resolve up to N distinct model+provider combinations.

    Uses the configured provider_priority to select models from different
    providers, maximizing provider diversity.
    """
    from research_agent.config import load_settings
    settings = load_settings()

    priority = settings.models.provider_priority
    models: list[dict[str, Any]] = []

    for prov in priority:
        if len(models) >= num_models:
            break

        if prov == "ollama":
            models.append({
                "model": f"ollama/{settings.models.subagent_local}",
                "extra": {"api_base": settings.ollama.api_base},
                "provider": "ollama",
            })
        elif prov == "openrouter":
            key = _resolve_api_key(settings.openrouter.api_key) or ""
            if not key:
                continue
            models.append({
                "model": settings.models.subagent_cloud,
                "extra": {"api_key": key},
                "provider": "openrouter",
            })
        elif prov == "nvidia":
            key = _resolve_api_key_from_env("NVIDIA_API_KEY") or _resolve_api_key_from_env("NVIDIA_NIMS_API_KEY")
            if not key:
                continue
            models.append({
                "model": settings.models.subagent_nvidia,
                "extra": {"api_key": key},
                "provider": "nvidia",
            })
        elif prov == "openai":
            key = _resolve_api_key(settings.openai.api_key) or ""
            if not key:
                continue
            extra: dict[str, Any] = {"api_key": key}
            if settings.openai.api_base:
                extra["api_base"] = settings.openai.api_base
            models.append({
                "model": settings.models.subagent_openai,
                "extra": extra,
                "provider": "openai",
            })
        elif prov == "anthropic":
            key = _resolve_api_key(settings.anthropic.api_key) or ""
            if not key:
                continue
            extra_a: dict[str, Any] = {"api_key": key}
            if settings.anthropic.api_base:
                extra_a["api_base"] = settings.anthropic.api_base
            models.append({
                "model": settings.models.subagent_anthropic,
                "extra": extra_a,
                "provider": "anthropic",
            })
        elif prov == "gemini":
            key = _resolve_api_key(settings.gemini.api_key) or ""
            if not key:
                continue
            extra_g: dict[str, Any] = {"api_key": key}
            if settings.gemini.api_base:
                extra_g["api_base"] = settings.gemini.api_base
            models.append({
                "model": settings.models.subagent_gemini,
                "extra": extra_g,
                "provider": "gemini",
            })
        elif prov == "groq":
            key = _resolve_api_key(settings.groq.api_key) or ""
            if not key:
                continue
            extra_gr: dict[str, Any] = {"api_key": key}
            if settings.groq.api_base:
                extra_gr["api_base"] = settings.groq.api_base
            models.append({
                "model": settings.models.subagent_groq,
                "extra": extra_gr,
                "provider": "groq",
            })

    return models[:num_models]


def _resolve_api_key(key_val: Any) -> str:
    """Extract a plain string API key from a SecretStr or raw string."""
    from pydantic import SecretStr
    if isinstance(key_val, SecretStr):
        return key_val.get_secret_value()
    return str(key_val or "")


def _resolve_api_key_from_env(var_name: str) -> str:
    """Read an API key from an environment variable."""
    import os
    return os.environ.get(var_name, "")


# ---------------------------------------------------------------------------
# Core parallel execution
# ---------------------------------------------------------------------------


async def _call_single_model(
    model_config: dict[str, Any],
    prompt: str,
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> ModelVote:
    """Call a single model with the given prompt and return its vote."""
    import time
    import litellm

    model_name = model_config["model"]
    provider = model_config["provider"]
    extra = model_config.get("extra", {})

    # Acquire rate limiter for cloud providers before making the call
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

    start = time.monotonic()
    try:
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            ),
            timeout=timeout_s,
        )
        latency = (time.monotonic() - start) * 1000

        text = response.choices[0].message.content or ""

        # Try to parse as JSON
        parsed: dict[str, Any] | list[Any] | None = None
        try:
            extracted = _extract_json(text)
            if extracted:
                parsed = json.loads(extracted)
        except (json.JSONDecodeError, Exception):
            pass

        return ModelVote(
            model_name=model_name,
            provider=provider,
            raw_text=text,
            parsed_json=parsed,
            latency_ms=round(latency, 1),
        )
    except asyncio.TimeoutError:
        latency = (time.monotonic() - start) * 1000
        return ModelVote(
            model_name=model_name,
            provider=provider,
            raw_text="",
            error=f"Timeout after {timeout_s}s",
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Ensemble model %s failed: %s: %s", model_name, type(e).__name__, e)
        return ModelVote(
            model_name=model_name,
            provider=provider,
            raw_text="",
            error=f"{type(e).__name__}: {e}",
            latency_ms=round(latency, 1),
        )


# ---------------------------------------------------------------------------
# Voting / Aggregation
# ---------------------------------------------------------------------------


def _majority_vote(votes: list[ModelVote]) -> EnsembleResult:
    """Majority vote: pick the most common discrete answer."""
    from collections import Counter

    valid_votes = [v for v in votes if v.error is None and v.raw_text.strip()]
    if not valid_votes:
        return _empty_result(VotingStrategy.MAJORITY, votes)

    # For JSON responses, compare serialized JSON
    texts = []
    for v in valid_votes:
        if v.parsed_json is not None:
            texts.append(json.dumps(v.parsed_json, sort_keys=True))
        else:
            texts.append(v.raw_text.strip()[:200])

    counter = Counter(texts)
    most_common = counter.most_common(1)
    majority_text = most_common[0][0] if most_common else ""
    majority_count = most_common[0][1] if most_common else 0
    consensus_score = majority_count / len(valid_votes) if valid_votes else 0.0

    # Find the winning vote
    winning_vote = valid_votes[0]
    for v in valid_votes:
        candidate = json.dumps(v.parsed_json, sort_keys=True) if v.parsed_json else v.raw_text.strip()[:200]
        if candidate == majority_text:
            winning_vote = v
            break

    return EnsembleResult(
        task_type="",
        strategy=VotingStrategy.MAJORITY,
        votes=votes,
        num_models=len(votes),
        num_success=len(valid_votes),
        num_failures=len(votes) - len(valid_votes),
        aggregated_text=winning_vote.raw_text,
        aggregated_json=winning_vote.parsed_json,
        consensus_score=round(consensus_score, 3),
        disagreement_detected=consensus_score < 0.6,
        disagreement_detail=_describe_disagreement(valid_votes, consensus_score) if consensus_score < 0.6 else "",
        total_latency_ms=round(sum(v.latency_ms for v in votes), 1),
    )


def _weighted_vote(votes: list[ModelVote]) -> EnsembleResult:
    """Weighted vote: average of numeric scores from valid responses.

    Expects each model's parsed_json to contain a 'score' key (float).
    Falls back to treating response length as a crude score.
    """
    valid_votes = [v for v in votes if v.error is None]
    if not valid_votes:
        return _empty_result(VotingStrategy.WEIGHTED, votes)

    scores: list[float] = []
    for v in valid_votes:
        if v.parsed_json and isinstance(v.parsed_json, dict):
            score = v.parsed_json.get("score") or v.parsed_json.get("confidence")
            if score is not None:
                try:
                    scores.append(float(score))
                    continue
                except (ValueError, TypeError):
                    pass
        # Fallback: use normalized response length as crude confidence
        scores.append(min(1.0, len(v.raw_text) / 1000))

    avg_score = sum(scores) / len(scores) if scores else 0.0
    std_dev = _std_dev(scores)

    # Find closest-to-average vote
    closest_idx = min(range(len(scores)), key=lambda i: abs(scores[i] - avg_score))
    closest_vote = valid_votes[closest_idx] if closest_idx < len(valid_votes) else valid_votes[0]

    return EnsembleResult(
        task_type="",
        strategy=VotingStrategy.WEIGHTED,
        votes=votes,
        num_models=len(votes),
        num_success=len(valid_votes),
        num_failures=len(votes) - len(valid_votes),
        aggregated_text=closest_vote.raw_text,
        aggregated_json={"score": round(avg_score, 3), "std_dev": round(std_dev, 3)},
        consensus_score=round(1.0 - min(1.0, std_dev / max(avg_score, 0.01)), 3),
        disagreement_detected=std_dev > 0.3,
        disagreement_detail=f"Score std_dev={std_dev:.3f}, avg={avg_score:.3f}" if std_dev > 0.3 else "",
        total_latency_ms=round(sum(v.latency_ms for v in votes), 1),
    )


def _consensus_vote(votes: list[ModelVote], threshold: float = 0.6) -> EnsembleResult:
    """Consensus vote: require threshold agreement.

    For JSON dicts, compares key-by-key agreement.
    For text, uses overlap coefficient.
    """
    valid_votes = [v for v in votes if v.error is None and v.raw_text.strip()]
    if not valid_votes:
        return _empty_result(VotingStrategy.CONSENSUS, votes)

    # Compute pairwise agreement
    total_pairs = 0
    agreeing_pairs = 0
    for i in range(len(valid_votes)):
        for j in range(i + 1, len(valid_votes)):
            total_pairs += 1
            if _votes_agree(valid_votes[i], valid_votes[j]):
                agreeing_pairs += 1

    consensus_score = agreeing_pairs / total_pairs if total_pairs > 0 else 0.0

    # Pick the most central vote (one with highest avg agreement to others)
    centrality_scores = []
    for i in range(len(valid_votes)):
        agreements = 0
        for j in range(len(valid_votes)):
            if i != j and _votes_agree(valid_votes[i], valid_votes[j]):
                agreements += 1
        centrality_scores.append(agreements / max(len(valid_votes) - 1, 1))

    best_idx = max(range(len(centrality_scores)), key=lambda i: centrality_scores[i])
    central_vote = valid_votes[best_idx] if best_idx < len(valid_votes) else valid_votes[0]

    return EnsembleResult(
        task_type="",
        strategy=VotingStrategy.CONSENSUS,
        votes=votes,
        num_models=len(votes),
        num_success=len(valid_votes),
        num_failures=len(votes) - len(valid_votes),
        aggregated_text=central_vote.raw_text,
        aggregated_json=central_vote.parsed_json,
        consensus_score=round(consensus_score, 3),
        disagreement_detected=consensus_score < threshold,
        disagreement_detail=_describe_disagreement(valid_votes, consensus_score) if consensus_score < threshold else "",
        total_latency_ms=round(sum(v.latency_ms for v in votes), 1),
    )


def _empty_result(strategy: VotingStrategy, votes: list[ModelVote]) -> EnsembleResult:
    """Return an empty result when no valid votes are available."""
    return EnsembleResult(
        task_type="",
        strategy=strategy,
        votes=votes,
        num_models=len(votes),
        num_success=0,
        num_failures=len(votes),
        aggregated_text="",
        aggregated_json=None,
        consensus_score=0.0,
        disagreement_detected=True,
        disagreement_detail="All models failed",
        total_latency_ms=round(sum(v.latency_ms for v in votes), 1),
    )


def _votes_agree(v1: ModelVote, v2: ModelVote) -> bool:
    """Check if two votes agree within tolerance."""
    # Both have JSON: deep compare
    if v1.parsed_json is not None and v2.parsed_json is not None:
        if isinstance(v1.parsed_json, dict) and isinstance(v2.parsed_json, dict):
            # Compare score/confidence fields
            s1 = v1.parsed_json.get("score") or v1.parsed_json.get("confidence")
            s2 = v2.parsed_json.get("score") or v2.parsed_json.get("confidence")
            if s1 is not None and s2 is not None:
                try:
                    return abs(float(s1) - float(s2)) < 0.2
                except (ValueError, TypeError):
                    pass
        # Fallback: compare serialized JSON equality
        return json.dumps(v1.parsed_json, sort_keys=True) == json.dumps(v2.parsed_json, sort_keys=True)

    # Text comparison: overlap coefficient
    words1 = set(v1.raw_text.lower().split())
    words2 = set(v2.raw_text.lower().split())
    if not words1 or not words2:
        return False
    intersection = words1 & words2
    overlap = len(intersection) / min(len(words1), len(words2))
    return overlap > 0.4


def _describe_disagreement(valid_votes: list[ModelVote], consensus_score: float) -> str:
    """Generate a human-readable description of disagreement among votes."""
    if not valid_votes:
        return "No valid votes to compare"

    parts = [f"Consensus score: {consensus_score:.2f}"]
    for i, v in enumerate(valid_votes):
        preview = v.raw_text[:100].replace("\n", " ")
        parts.append(f"  Model {i+1} ({v.provider}/{v.model_name.split('/')[-1]}): {preview}...")
    return "\n".join(parts)


def _std_dev(values: list[float]) -> float:
    """Compute population standard deviation."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_ensemble(
    task_type: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    strategy: VotingStrategy | None = None,
    num_models: int | None = None,
    timeout_s: float | None = None,
    model_resolver: Callable[[int], list[dict[str, Any]]] | None = None,
) -> EnsembleResult:
    """Run an ensemble voting round.

    Args:
        task_type: Type of task (critic, planner, composer, etc.)
        prompt: The prompt to send to all models
        system_prompt: Optional system prompt
        temperature: Temperature for generation
        max_tokens: Max tokens per model
        strategy: Override voting strategy (default: from config)
        num_models: Override number of models (default: from config)
        timeout_s: Override timeout per model (default: from config)
        model_resolver: Override model resolver function

    Returns:
        EnsembleResult with aggregated votes
    """
    strat, n_models, min_success, to = get_ensemble_config(task_type)
    strategy = strategy or strat
    num_models = num_models or n_models
    timeout_s = timeout_s or to

    resolver = model_resolver or _resolve_ensemble_models
    model_configs = resolver(num_models)

    if not model_configs:
        logger.warning("Ensemble: No models configured for task '%s'", task_type)
        return EnsembleResult(
            task_type=task_type,
            strategy=strategy,
            num_models=0,
            aggregated_text="",
            consensus_score=0.0,
            disagreement_detected=True,
            disagreement_detail="No models available",
        )

    # Call all models in parallel
    tasks = [
        _call_single_model(mc, prompt, system_prompt, temperature, max_tokens, timeout_s)
        for mc in model_configs
    ]
    votes = await asyncio.gather(*tasks)

    # Apply voting strategy
    if strategy == VotingStrategy.MAJORITY:
        result = _majority_vote(votes)
    elif strategy == VotingStrategy.WEIGHTED:
        result = _weighted_vote(votes)
    elif strategy == VotingStrategy.CONSENSUS:
        result = _consensus_vote(votes)
    else:
        result = _majority_vote(votes)

    result.task_type = task_type
    result.strategy = strategy

    # Check minimum success threshold
    if result.num_success < min_success:
        logger.warning(
            "Ensemble '%s': %d/%d models succeeded (need %d)",
            task_type, result.num_success, result.num_models, min_success,
        )

    logger.info(
        "Ensemble '%s': strategy=%s, models=%d, success=%d, consensus=%.2f, total_latency=%.0fms",
        task_type, strategy.value, result.num_models, result.num_success,
        result.consensus_score, result.total_latency_ms,
    )

    return result


async def run_json_ensemble(
    task_type: str,
    prompt: str,
    system_prompt: str = "You are a research assistant that only outputs valid JSON. No markdown, no explanation, just the JSON object.",
    temperature: float = 0.1,
    max_tokens: int = 4096,
    strategy: VotingStrategy | None = None,
    num_models: int | None = None,
    timeout_s: float | None = None,
) -> EnsembleResult:
    """Run ensemble voting expecting JSON responses from all models.

    Same as run_ensemble but with JSON-specific defaults (lower temperature,
    higher max_tokens, JSON system prompt).
    """
    return await run_ensemble(
        task_type=task_type,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        strategy=strategy,
        num_models=num_models,
        timeout_s=timeout_s,
    )
