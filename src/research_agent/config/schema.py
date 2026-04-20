from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeSettings(BaseModel):
    """Runtime configuration for research agent execution."""
    mode: Literal["api_only", "parallel", "async"] = "parallel"
    max_iterations: int = Field(default=4, ge=1, le=20)
    max_runtime_minutes: int = Field(default=25, ge=1)
    max_cost_usd: float = Field(default=5.0, ge=0)
    parallel_workers: int = Field(default=4, ge=1, le=8, description="Max concurrent subagent workers")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        supported = {"api_only", "parallel", "async"}
        if value not in supported:
            raise ValueError(f"mode must be one of: {sorted(supported)}")
        return value


class ModelSettings(BaseModel):
    """Model configuration with multi-provider support.

    Role definitions:
    - orchestrator: Local model for planning, clarification, critic. Default: ollama/qwen3:8b
    - subagent: Model for section synthesis (auto-selects from local/cloud/fallback)
    - provider_priority: Order of providers to try (ollama > openrouter > puter)
    """
    # Orchestrator (head) model
    orchestrator_model: str = "ollama/qwen3:8b"
    orchestrator_provider: Literal["ollama", "openrouter"] = "ollama"

    # Subagent model settings
    subagent_provider: Literal["auto", "ollama", "openrouter", "puter"] = "auto"
    subagent_local: str = "deepseek-r1:8b"
    subagent_cloud: str = "openrouter/free"

    # Provider priority
    provider_priority: list[str] = Field(
        default_factory=lambda: ["ollama", "openrouter", "puter"]
    )

    # Legacy aliases (deprecated, for backward compatibility)
    head_model: str = ""
    subagent_model: str = ""
    worker_model: str = ""
    strong_model: str = ""

    @field_validator("provider_priority")
    @classmethod
    def validate_provider_priority(cls, value: list[str]) -> list[str]:
        supported = {"ollama", "openrouter", "puter"}
        for p in value:
            if p not in supported:
                raise ValueError(f"Invalid provider in priority: {p}. Supported: {sorted(supported)}")
        return value


class OutputSettings(BaseModel):
    """Output/templating configuration."""
    default_template: str = "ieee-2col"
    supported_templates: list[str] = Field(
        default_factory=lambda: ["ieee-1col", "ieee-2col", "acm", "springer"]
    )
    default_columns: Literal[1, 2] = 2
    language: str = "en"

    @model_validator(mode="after")
    def validate_template_config(self) -> "OutputSettings":
        if self.default_template not in self.supported_templates:
            raise ValueError(
                f"default_template '{self.default_template}' must be in supported_templates"
            )
        # Infer columns from template name if not explicitly set
        if "2col" in self.default_template:
            self.default_columns = 2
        else:
            self.default_columns = 1
        return self


class RetrievalSettings(BaseModel):
    """Retrieval and search configuration."""
    web_provider: str = "hybrid"
    web_search_depth: Literal["fast", "balanced", "advanced"] = "advanced"
    paper_providers: list[str] = Field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex"]
    )
    max_papers_per_section: int = Field(default=15, ge=1, le=50)
    chunk_size: int = Field(default=1024, ge=256, le=4096)
    chunk_overlap: int = Field(default=128, ge=0, le=512)
    allow_metadata_fallback: bool = True
    metadata_fallback_confidence_penalty: float = Field(default=0.15, ge=0, le=1)
    enable_fuzzy_dedup: bool = True

    @field_validator("paper_providers")
    @classmethod
    def validate_paper_providers(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("paper_providers cannot be empty")
        supported = {"arxiv", "semantic_scholar", "openalex", "pubmed"}
        for p in value:
            if p not in supported:
                raise ValueError(f"Unsupported paper provider: {p}. Supported: {sorted(supported)}")
        return value

    @field_validator("web_provider")
    @classmethod
    def validate_web_provider(cls, value: str) -> str:
        supported = {"tavily", "duckduckgo", "browser_use", "hybrid", "scrape"}
        if value not in supported:
            raise ValueError(f"web_provider must be one of: {sorted(supported)}")
        return value


class OllamaSettings(BaseModel):
    """Ollama-specific configuration."""
    api_base: str = "http://localhost:11434"
    num_parallel: int = Field(default=4, ge=1, le=16)
    max_loaded_models: int = Field(default=2, ge=1, le=4)
    timeout_seconds: int = Field(default=120, ge=30, le=300)


class OpenRouterSettings(BaseModel):
    """OpenRouter configuration."""
    api_key: str = ""
    timeout_seconds: int = Field(default=60, ge=10, le=180)


class FeatureFlags(BaseModel):
    """Feature flags for v2 features."""
    parallel_subagents: bool = True
    cite_autofix: bool = True
    session_persistence: Literal["localStorage", "redis", "none"] = "localStorage"
    enable_session_persistence: bool = True
    pdf_export: bool = False
    multi_language: bool = False


class ObservabilitySettings(BaseModel):
    """Observability and monitoring configuration."""
    enable_tracing: bool = False
    enable_metrics: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class AppSettings(BaseModel):
    """Main application settings."""
    version: str = "2.0"
    runtime: RuntimeSettings
    models: ModelSettings
    output: OutputSettings
    retrieval: RetrievalSettings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
