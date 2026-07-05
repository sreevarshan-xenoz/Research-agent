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

    # OpenAI settings
    if env.get("OPENAI_API_KEY"):
        data.setdefault("openai", {})["api_key"] = env["OPENAI_API_KEY"]
    if env.get("OPENAI_API_BASE"):
        data.setdefault("openai", {})["api_base"] = env["OPENAI_API_BASE"]
    if env.get("OPENAI_ORGANIZATION"):
        data.setdefault("openai", {})["organization"] = env["OPENAI_ORGANIZATION"]

    # Anthropic settings
    if env.get("ANTHROPIC_API_KEY"):
        data.setdefault("anthropic", {})["api_key"] = env["ANTHROPIC_API_KEY"]

    # Gemini settings
    if env.get("GEMINI_API_KEY"):
        data.setdefault("gemini", {})["api_key"] = env["GEMINI_API_KEY"]
    if env.get("GEMINI_API_BASE"):
        data.setdefault("gemini", {})["api_base"] = env["GEMINI_API_BASE"]

    # Groq settings
    if env.get("GROQ_API_KEY"):
        data.setdefault("groq", {})["api_key"] = env["GROQ_API_KEY"]

    # Observability settings (P17)
    if env.get("OBSERVABILITY_ENABLED"):
        val = env["OBSERVABILITY_ENABLED"].lower().strip()
        data.setdefault("observability", {})["enabled"] = val in ("true", "1", "yes")
    if env.get("OBSERVABILITY_LOG_LEVEL"):
        data.setdefault("observability", {})["log_level"] = env["OBSERVABILITY_LOG_LEVEL"].upper()
    if env.get("OBSERVABILITY_JSON_LOGGING"):
        val = env["OBSERVABILITY_JSON_LOGGING"].lower().strip()
        data.setdefault("observability", {})["json_logging"] = val in ("true", "1", "yes")
    if env.get("OBSERVABILITY_ENABLE_METRICS"):
        val = env["OBSERVABILITY_ENABLE_METRICS"].lower().strip()
        data.setdefault("observability", {})["enable_metrics"] = val in ("true", "1", "yes")
    if env.get("OBSERVABILITY_METRICS_PORT"):
        data.setdefault("observability", {})["metrics_port"] = int(env["OBSERVABILITY_METRICS_PORT"])
    if env.get("OTLP_ENDPOINT"):
        data.setdefault("observability", {})["otlp_endpoint"] = env["OTLP_ENDPOINT"]
    if env.get("SENTRY_DSN"):
        data.setdefault("observability", {})["sentry_dsn"] = env["SENTRY_DSN"]

    # Subagent model overrides for new providers
    if env.get("SUBAGENT_OPENAI_MODEL"):
        models["subagent_openai"] = env["SUBAGENT_OPENAI_MODEL"]
    if env.get("SUBAGENT_ANTHROPIC_MODEL"):
        models["subagent_anthropic"] = env["SUBAGENT_ANTHROPIC_MODEL"]
    if env.get("SUBAGENT_GEMINI_MODEL"):
        models["subagent_gemini"] = env["SUBAGENT_GEMINI_MODEL"]
    if env.get("SUBAGENT_GROQ_MODEL"):
        models["subagent_groq"] = env["SUBAGENT_GROQ_MODEL"]

    # vLLM settings
    if env.get("VLLM_API_KEY"):
        data.setdefault("vllm", {})["api_key"] = env["VLLM_API_KEY"]
    if env.get("VLLM_API_BASE"):
        data.setdefault("vllm", {})["api_base"] = env["VLLM_API_BASE"]

    # Model router settings
    if env.get("MODEL_ROUTER_ENABLED"):
        val = env["MODEL_ROUTER_ENABLED"].lower().strip()
        data.setdefault("model_router", {})["enabled"] = val in ("true", "1", "yes")
    if env.get("MODEL_ROUTER_DEFAULT_PROVIDER"):
        data.setdefault("model_router", {})["default_provider"] = env["MODEL_ROUTER_DEFAULT_PROVIDER"]
    if env.get("MODEL_ROUTER_DEFAULT_MODEL"):
        data.setdefault("model_router", {})["default_model"] = env["MODEL_ROUTER_DEFAULT_MODEL"]

    # P18: Security settings
    if env.get("SECRET_KEY"):
        data.setdefault("auth", {})["secret_key"] = env["SECRET_KEY"]

    # RBAC settings
    rbac = data.setdefault("rbac", {})
    if env.get("RBAC_ENABLED"):
        rbac["enabled"] = env["RBAC_ENABLED"].lower().strip() in ("true", "1", "yes")
    if env.get("RBAC_DEFAULT_ROLE"):
        rbac["default_role"] = env["RBAC_DEFAULT_ROLE"].lower().strip()

    # Rate limiting settings
    rate_limit = data.setdefault("rate_limit", {})
    if env.get("RATE_LIMIT_ENABLED"):
        rate_limit["enabled"] = env["RATE_LIMIT_ENABLED"].lower().strip() in ("true", "1", "yes")
    if env.get("RATE_LIMIT_DEFAULT_RPM"):
        rate_limit["default_requests_per_minute"] = int(env["RATE_LIMIT_DEFAULT_RPM"])
    if env.get("RATE_LIMIT_AUTH_RPM"):
        rate_limit["authenticated_requests_per_minute"] = int(env["RATE_LIMIT_AUTH_RPM"])
    if env.get("RATE_LIMIT_ADMIN_RPM"):
        rate_limit["admin_requests_per_minute"] = int(env["RATE_LIMIT_ADMIN_RPM"])

    # Audit logging settings
    audit = data.setdefault("audit", {})
    if env.get("AUDIT_ENABLED"):
        audit["enabled"] = env["AUDIT_ENABLED"].lower().strip() in ("true", "1", "yes")
    if env.get("AUDIT_RETENTION_DAYS"):
        audit["retention_days"] = int(env["AUDIT_RETENTION_DAYS"])
    if env.get("AUDIT_LOG_BODY"):
        audit["log_request_body"] = env["AUDIT_LOG_BODY"].lower().strip() in ("true", "1", "yes")

    # SSO/OAuth settings
    sso = data.setdefault("sso", {})
    if env.get("SSO_ENABLED"):
        sso["enabled"] = env["SSO_ENABLED"].lower().strip() in ("true", "1", "yes")
    if env.get("GOOGLE_CLIENT_ID"):
        sso["google_client_id"] = env["GOOGLE_CLIENT_ID"]
    if env.get("GOOGLE_CLIENT_SECRET"):
        sso["google_client_secret"] = env["GOOGLE_CLIENT_SECRET"]
    if env.get("GITHUB_CLIENT_ID"):
        sso["github_client_id"] = env["GITHUB_CLIENT_ID"]
    if env.get("GITHUB_CLIENT_SECRET"):
        sso["github_client_secret"] = env["GITHUB_CLIENT_SECRET"]
    if env.get("ORCID_CLIENT_ID"):
        sso["orcid_client_id"] = env["ORCID_CLIENT_ID"]
    if env.get("ORCID_CLIENT_SECRET"):
        sso["orcid_client_secret"] = env["ORCID_CLIENT_SECRET"]

    # Secrets management
    secrets_mgmt = data.setdefault("secrets_mgmt", {})
    if env.get("ENCRYPTION_KEY"):
        secrets_mgmt["encryption_key"] = env["ENCRYPTION_KEY"]
    if env.get("ENCRYPT_API_KEYS"):
        secrets_mgmt["encrypt_api_keys_at_rest"] = env["ENCRYPT_API_KEYS"].lower().strip() in ("true", "1", "yes")

    # Watchdog email / SMTP settings
    watchdog_email = data.setdefault("watchdog_email", {})
    if env.get("SMTP_HOST"):
        watchdog_email["smtp_host"] = env["SMTP_HOST"]
    if env.get("SMTP_PORT"):
        watchdog_email["smtp_port"] = int(env["SMTP_PORT"])
    if env.get("SMTP_USER"):
        watchdog_email["smtp_user"] = env["SMTP_USER"]
    if env.get("SMTP_PASSWORD"):
        watchdog_email["smtp_password"] = env["SMTP_PASSWORD"]
    if env.get("WATCHDOG_FROM_EMAIL"):
        watchdog_email["from_email"] = env["WATCHDOG_FROM_EMAIL"]
    if env.get("WATCHDOG_FROM_NAME"):
        watchdog_email["from_name"] = env["WATCHDOG_FROM_NAME"]

    # Code Sandbox settings (P24)
    code_sandbox = data.setdefault("code_sandbox", {})
    if env.get("CODE_SANDBOX_ENABLED"):
        val = env["CODE_SANDBOX_ENABLED"].lower().strip()
        code_sandbox["enabled"] = val in ("true", "1", "yes")
    if env.get("CODE_SANDBOX_TIMEOUT"):
        code_sandbox["container_timeout"] = int(env["CODE_SANDBOX_TIMEOUT"])
    if env.get("CODE_SANDBOX_MEMORY_MB"):
        code_sandbox["memory_limit_mb"] = int(env["CODE_SANDBOX_MEMORY_MB"])
    if env.get("CODE_SANDBOX_POOL_SIZE"):
        code_sandbox["pool_size"] = int(env["CODE_SANDBOX_POOL_SIZE"])

    # Multi-modal settings (P22)
    multi_modal = data.setdefault("multi_modal", {})
    if env.get("MULTI_MODAL_ENABLED"):
        val = env["MULTI_MODAL_ENABLED"].lower().strip()
        multi_modal["enabled"] = val in ("true", "1", "yes")
    if env.get("MULTI_MODAL_EXTRACT_FIGURES"):
        val = env["MULTI_MODAL_EXTRACT_FIGURES"].lower().strip()
        multi_modal["extract_figures"] = val in ("true", "1", "yes")
    if env.get("MULTI_MODAL_EXTRACT_TABLES"):
        val = env["MULTI_MODAL_EXTRACT_TABLES"].lower().strip()
        multi_modal["extract_tables"] = val in ("true", "1", "yes")
    if env.get("MULTI_MODAL_EXTRACT_EQUATIONS"):
        val = env["MULTI_MODAL_EXTRACT_EQUATIONS"].lower().strip()
        multi_modal["extract_equations"] = val in ("true", "1", "yes")
    if env.get("MULTI_MODAL_MAX_FIGURES"):
        multi_modal["max_figures"] = int(env["MULTI_MODAL_MAX_FIGURES"])
    if env.get("MULTI_MODAL_MAX_TABLES"):
        multi_modal["max_tables"] = int(env["MULTI_MODAL_MAX_TABLES"])
    if env.get("MULTI_MODAL_MAX_EQUATIONS"):
        multi_modal["max_equations"] = int(env["MULTI_MODAL_MAX_EQUATIONS"])
    if env.get("PIX2TEXT_ENABLED"):
        val = env["PIX2TEXT_ENABLED"].lower().strip()
        multi_modal["pix2text_enabled"] = val in ("true", "1", "yes")

    # Template Library settings (P39)
    template_library = data.setdefault("template_library", {})
    if env.get("TEMPLATE_LIBRARY_ENABLED"):
        val = env["TEMPLATE_LIBRARY_ENABLED"].lower().strip()
        template_library["enabled"] = val in ("true", "1", "yes")
    if env.get("TEMPLATE_LIBRARY_DEFAULT_TEMPLATE"):
        template_library["default_template_id"] = env["TEMPLATE_LIBRARY_DEFAULT_TEMPLATE"]
    if env.get("TEMPLATE_LIBRARY_DEFAULT_PRESET"):
        template_library["default_preset_id"] = env["TEMPLATE_LIBRARY_DEFAULT_PRESET"]
    if env.get("TEMPLATE_LIBRARY_STORE_PATH"):
        template_library["store_path"] = env["TEMPLATE_LIBRARY_STORE_PATH"]

    # Ensemble settings (P31)
    ensemble = data.setdefault("ensemble", {})
    if env.get("ENSEMBLE_ENABLED"):
        val = env["ENSEMBLE_ENABLED"].lower().strip()
        ensemble["enabled"] = val in ("true", "1", "yes")
    if env.get("ENSEMBLE_NUM_MODELS"):
        ensemble["default_num_models"] = int(env["ENSEMBLE_NUM_MODELS"])
    if env.get("ENSEMBLE_TIMEOUT"):
        ensemble["default_timeout_s"] = float(env["ENSEMBLE_TIMEOUT"])
    if env.get("ENSEMBLE_MIN_SUCCESS_RATIO"):
        ensemble["min_success_ratio"] = float(env["ENSEMBLE_MIN_SUCCESS_RATIO"])

    # Job Queue settings (P16)
    job_queue = data.setdefault("job_queue", {})
    if env.get("JOB_QUEUE_ENABLED"):
        val = env["JOB_QUEUE_ENABLED"].lower().strip()
        job_queue["enabled"] = val in ("true", "1", "yes")
    if env.get("JOB_QUEUE_WORKER_COUNT"):
        job_queue["worker_count"] = int(env["JOB_QUEUE_WORKER_COUNT"])
    if env.get("JOB_QUEUE_MAX_CONCURRENT"):
        job_queue["max_concurrent_per_user"] = int(env["JOB_QUEUE_MAX_CONCURRENT"])
    if env.get("JOB_QUEUE_TIMEOUT"):
        job_queue["default_timeout"] = int(env["JOB_QUEUE_TIMEOUT"])

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
