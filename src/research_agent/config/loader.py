from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
import yaml  # type: ignore[import-untyped]

from research_agent.config.schema import AppSettings

DEFAULT_SETTINGS_PATH = Path("configs/settings.yaml")
EXAMPLE_SETTINGS_PATH = Path("configs/settings.example.yaml")


def _coerce_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_env_overrides(data: dict, env: Mapping[str, str]) -> dict:
    runtime = data.setdefault("runtime", {})
    models = data.setdefault("models", {})
    output = data.setdefault("output", {})
    retrieval = data.setdefault("retrieval", {})
    ollama = data.setdefault("ollama", {})
    openrouter = data.setdefault("openrouter", {})

    if env.get("MAX_ITERATIONS"):
        runtime["max_iterations"] = int(env["MAX_ITERATIONS"])
    if env.get("MAX_RUNTIME_MINUTES"):
        runtime["max_runtime_minutes"] = int(env["MAX_RUNTIME_MINUTES"])
    if env.get("MAX_COST_USD"):
        runtime["max_cost_usd"] = float(env["MAX_COST_USD"])
    if env.get("PARALLEL_WORKERS"):
        runtime["parallel_workers"] = int(env["PARALLEL_WORKERS"])
    if env.get("INTERACTIVE_CHECKPOINTS"):
        val = env["INTERACTIVE_CHECKPOINTS"].lower().strip()
        runtime["interactive_checkpoints"] = val in ("true", "1", "yes")

    # v2 Model Routing
    if env.get("ORCHESTRATOR_MODEL"):
        models["orchestrator_model"] = env["ORCHESTRATOR_MODEL"]
    if env.get("SUBAGENT_LOCAL_MODEL"):
        models["subagent_local"] = env["SUBAGENT_LOCAL_MODEL"]
    if env.get("SUBAGENT_CLOUD_MODEL"):
        models["subagent_cloud"] = env["SUBAGENT_CLOUD_MODEL"]
    if env.get("SUBAGENT_NVIDIA_MODEL"):
        models["subagent_nvidia"] = env["SUBAGENT_NVIDIA_MODEL"]
    elif env.get("NVIDIA_MODEL"):
        models["subagent_nvidia"] = env["NVIDIA_MODEL"]
    if env.get("MODEL_PROVIDER_PRIORITY"):
        models["provider_priority"] = _coerce_list(env["MODEL_PROVIDER_PRIORITY"])

    # Ollama settings
    if env.get("OLLAMA_API_BASE"):
        ollama["api_base"] = env["OLLAMA_API_BASE"]
    if env.get("OLLAMA_NUM_PARALLEL"):
        ollama["num_parallel"] = int(env["OLLAMA_NUM_PARALLEL"])

    # OpenRouter settings
    if env.get("OPENROUTER_API_KEY"):
        openrouter["api_key"] = env["OPENROUTER_API_KEY"]

    # Legacy aliases (deprecated)
    if env.get("HEAD_MODEL"):
        models["head_model"] = env["HEAD_MODEL"]
        models["orchestrator_model"] = env["HEAD_MODEL"]
    if env.get("SUBAGENT_MODEL"):
        models["subagent_model"] = env["SUBAGENT_MODEL"]
        models["subagent_cloud"] = env["SUBAGENT_MODEL"]
    if env.get("WORKER_MODEL"):
        models["worker_model"] = env["WORKER_MODEL"]
        models["subagent_local"] = env["WORKER_MODEL"]
    if env.get("STRONG_MODEL"):
        models["strong_model"] = env["STRONG_MODEL"]
        models["subagent_cloud"] = env["STRONG_MODEL"]
    if env.get("LITELLM_DEFAULT_MODEL"):
        models["worker_model"] = env["LITELLM_DEFAULT_MODEL"]
        models["subagent_local"] = env["LITELLM_DEFAULT_MODEL"]
    if env.get("LITELLM_STRONG_MODEL"):
        models["strong_model"] = env["LITELLM_STRONG_MODEL"]
        models["subagent_cloud"] = env["LITELLM_STRONG_MODEL"]

    if env.get("DEFAULT_TEMPLATE"):
        output["default_template"] = env["DEFAULT_TEMPLATE"]
    if env.get("SUPPORTED_TEMPLATES"):
        output["supported_templates"] = _coerce_list(env["SUPPORTED_TEMPLATES"])
    if env.get("DEFAULT_ACM_LAYOUT"):
        output["default_acm_layout"] = env["DEFAULT_ACM_LAYOUT"]

    if env.get("REDIS_URL"):
        data.setdefault("redis", {})["url"] = env["REDIS_URL"]
    if env.get("QDRANT_LOCATION"):
        data.setdefault("qdrant", {})["location"] = env["QDRANT_LOCATION"]

    if env.get("WEB_PROVIDER"):
        retrieval["web_provider"] = env["WEB_PROVIDER"]
    if env.get("PAPER_PROVIDERS"):
        retrieval["paper_providers"] = _coerce_list(env["PAPER_PROVIDERS"])

    # vLLM settings
    if env.get("VLLM_API_KEY"):
        data.setdefault("vllm", {})["api_key"] = env["VLLM_API_KEY"]
    if env.get("VLLM_API_BASE"):
        data.setdefault("vllm", {})["api_base"] = env["VLLM_API_BASE"]

    # Auth settings
    if env.get("SECRET_KEY"):
        data.setdefault("auth", {})["secret_key"] = env["SECRET_KEY"]

    return data


def _read_yaml_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Settings file must contain a YAML object: {path}")
    return loaded


def resolve_settings_path(settings_path: str | Path | None = None) -> Path:
    if settings_path is not None:
        candidate = Path(settings_path)
        if not candidate.exists():
            raise FileNotFoundError(f"Settings file not found: {candidate}")
        return candidate

    if DEFAULT_SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS_PATH
    if EXAMPLE_SETTINGS_PATH.exists():
        return EXAMPLE_SETTINGS_PATH

    raise FileNotFoundError(
        f"No settings file found. Expected one of: {DEFAULT_SETTINGS_PATH} or {EXAMPLE_SETTINGS_PATH}"
    )


DEV_SECRET_WARNING = """
****************************************************************
* WARNING: Using development JWT signing key!                 *
* Set SECRET_KEY environment variable with a strong secret.   *
* Generate one: python -c "import secrets;                   *
*     print(secrets.token_urlsafe(32))"                       *
*                                                              *
* DO NOT DEPLOY TO PRODUCTION WITH THIS DEFAULT.              *
****************************************************************
"""


def validate_insecure_defaults(settings: AppSettings) -> None:
    """Emit warnings for known insecure default secret values.

    Call once at application startup, not on every request.
    """
    import warnings

    secret = str(settings.auth.secret_key)
    if not secret or secret == "DEV_SECRET_DO_NOT_USE_IN_PROD":
        warnings.warn(DEV_SECRET_WARNING, RuntimeWarning, stacklevel=2)

    # Check other secrets are configured when features that need them are enabled
    if settings.features.session_persistence == "redis":
        if not settings.redis.url or settings.redis.url == "redis://localhost:6379":
            warnings.warn(
                "Session persistence is set to 'redis' but using default localhost URL. "
                "Set redis.url in settings.yaml or REDIS_URL env var for production.",
                RuntimeWarning,
                stacklevel=2,
            )


def load_settings(
    settings_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AppSettings:
    # Load local .env for developer-friendly provider key/model configuration.
    load_dotenv(override=False)

    env_map = dict(os.environ if env is None else env)
    path = resolve_settings_path(settings_path)
    data = _read_yaml_file(path)
    data = _apply_env_overrides(data, env_map)
    return AppSettings.model_validate(data)
