from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeSettings(BaseModel):
    mode: str = "api_only"
    max_iterations: int = Field(default=4, ge=1, le=20)
    max_runtime_minutes: int = Field(default=25, ge=1)
    max_cost_usd: float = Field(default=5.0, ge=0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value != "api_only":
            raise ValueError("v1 supports only api_only runtime mode")
        return value


class ModelSettings(BaseModel):
    """Model configuration with clear role mappings.

    Role definitions:
    - head: Local model for orchestration (planning, clarification, critic). Default: ollama/gemma4:e4b
    - subagent: Cloud model for heavy generation (section synthesis, LaTeX composition). Default: auto-select from OPENROUTER/NVIDIA keys
    - worker_model: Legacy alias for backward compatibility
    - strong_model: Legacy alias for backward compatibility
    """
    head_model: str = "ollama/gemma4:e4b"  # Local orchestrator
    subagent_model: str = ""  # Cloud model for heavy tasks (auto-select if empty)
    worker_model: str = ""  # Legacy alias
    strong_model: str = ""  # Legacy alias


class OutputSettings(BaseModel):
    default_template: str = "ieee"
    supported_templates: list[str] = Field(default_factory=lambda: ["ieee", "acm"])

    @model_validator(mode="after")
    def validate_default_in_supported(self) -> "OutputSettings":
        if self.default_template not in self.supported_templates:
            raise ValueError(f"default_template '{self.default_template}' must be in supported_templates")
        return self

    @model_validator(mode="after")
    def validate_default_template(self) -> "OutputSettings":
        if self.default_template not in self.supported_templates:
            raise ValueError("default_template must exist in supported_templates")
        return self


class RetrievalSettings(BaseModel):
    web_provider: str = "duckduckgo"
    paper_providers: list[str] = Field(default_factory=lambda: ["arxiv", "semantic_scholar", "openalex"])
    allow_metadata_fallback: bool = True
    metadata_fallback_confidence_penalty: float = Field(default=0.15, ge=0, le=1)

    @field_validator("paper_providers")
    @classmethod
    def validate_paper_providers(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("paper_providers cannot be empty")
        supported = {"arxiv", "semantic_scholar", "openalex"}
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


class AppSettings(BaseModel):
    runtime: RuntimeSettings
    models: ModelSettings
    output: OutputSettings
    retrieval: RetrievalSettings
