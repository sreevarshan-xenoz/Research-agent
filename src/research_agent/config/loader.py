from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
import yaml

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

    if env.get("MAX_ITERATIONS"):
        runtime["max_iterations"] = int(env["MAX_ITERATIONS"])
    if env.get("MAX_RUNTIME_MINUTES"):
        runtime["max_runtime_minutes"] = int(env["MAX_RUNTIME_MINUTES"])
    if env.get("MAX_COST_USD"):
        runtime["max_cost_usd"] = float(env["MAX_COST_USD"])

    if env.get("LITELLM_DEFAULT_MODEL"):
        models["worker_model"] = env["LITELLM_DEFAULT_MODEL"]
    if env.get("WORKER_MODEL"):
        models["worker_model"] = env["WORKER_MODEL"]

    if env.get("LITELLM_STRONG_MODEL"):
        models["strong_model"] = env["LITELLM_STRONG_MODEL"]
    if env.get("STRONG_MODEL"):
        models["strong_model"] = env["STRONG_MODEL"]

    # Hybrid multi-model settings
    if env.get("HEAD_MODEL"):
        models["head_model"] = env["HEAD_MODEL"]
    if env.get("SUBAGENT_MODEL"):
        models["subagent_model"] = env["SUBAGENT_MODEL"]

    if env.get("DEFAULT_TEMPLATE"):
        output["default_template"] = env["DEFAULT_TEMPLATE"]
    if env.get("SUPPORTED_TEMPLATES"):
        output["supported_templates"] = _coerce_list(env["SUPPORTED_TEMPLATES"])

    if env.get("WEB_PROVIDER"):
        retrieval["web_provider"] = env["WEB_PROVIDER"]
    if env.get("PAPER_PROVIDERS"):
        retrieval["paper_providers"] = _coerce_list(env["PAPER_PROVIDERS"])

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
