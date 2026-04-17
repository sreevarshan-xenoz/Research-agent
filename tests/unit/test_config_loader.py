from pathlib import Path

import pytest

from research_agent.config.loader import load_settings, resolve_settings_path


def test_resolve_settings_uses_example_when_default_missing() -> None:
    resolved = resolve_settings_path()
    assert resolved.name in {"settings.yaml", "settings.example.yaml"}


def test_load_settings_reads_example_values() -> None:
    settings = load_settings()
    assert settings.runtime.mode == "api_only"
    assert settings.output.default_template in settings.output.supported_templates


def test_load_settings_env_overrides(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
runtime:
  mode: api_only
  max_iterations: 2
  max_runtime_minutes: 10
  max_cost_usd: 1.0
models:
  worker_model: old-worker
  strong_model: old-strong
output:
  default_template: ieee
  supported_templates:
    - ieee
    - acm
retrieval:
  web_provider: tavily
  paper_providers:
    - arxiv
  allow_metadata_fallback: true
  metadata_fallback_confidence_penalty: 0.1
""".strip(),
        encoding="utf-8",
    )

    env = {
        "MAX_ITERATIONS": "5",
        "LITELLM_DEFAULT_MODEL": "worker-new",
        "LITELLM_STRONG_MODEL": "strong-new",
        "DEFAULT_TEMPLATE": "acm",
        "SUPPORTED_TEMPLATES": "ieee,acm",
        "PAPER_PROVIDERS": "arxiv,semantic_scholar",
    }
    settings = load_settings(settings_path=settings_file, env=env)

    assert settings.runtime.max_iterations == 5
    assert settings.models.worker_model == "worker-new"
    assert settings.models.strong_model == "strong-new"
    assert settings.output.default_template == "acm"
    assert settings.retrieval.paper_providers == ["arxiv", "semantic_scholar"]


def test_load_settings_rejects_invalid_mode(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
runtime:
  mode: local
  max_iterations: 4
  max_runtime_minutes: 10
  max_cost_usd: 1.0
models:
  worker_model: m1
  strong_model: m2
output:
  default_template: ieee
  supported_templates:
    - ieee
retrieval:
  web_provider: tavily
  paper_providers:
    - arxiv
  allow_metadata_fallback: true
  metadata_fallback_confidence_penalty: 0.1
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        load_settings(settings_path=settings_file)


def test_load_settings_model_alias_overrides(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
runtime:
  mode: api_only
  max_iterations: 2
  max_runtime_minutes: 10
  max_cost_usd: 1.0
models:
  worker_model: old-worker
  strong_model: old-strong
output:
  default_template: ieee
  supported_templates:
    - ieee
    - acm
retrieval:
  web_provider: tavily
  paper_providers:
    - arxiv
  allow_metadata_fallback: true
  metadata_fallback_confidence_penalty: 0.1
""".strip(),
        encoding="utf-8",
    )

    env = {
        "WORKER_MODEL": "openrouter/meta-llama/llama-3.1-8b-instruct",
        "STRONG_MODEL": "nvidia_nim/meta/llama-3.1-70b-instruct",
    }
    settings = load_settings(settings_path=settings_file, env=env)

    assert settings.models.worker_model == "openrouter/meta-llama/llama-3.1-8b-instruct"
    assert settings.models.strong_model == "nvidia_nim/meta/llama-3.1-70b-instruct"
