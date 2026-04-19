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
    worker_model: str
    strong_model: str
    head_model: str = ""  # Local orchestrator (e.g. "ollama/gemma4:e4b")
    subagent_model: str = ""  # Cloud model for heavy tasks (e.g. "openrouter/openrouter/free")


class OutputSettings(BaseModel):
    default_template: str = "ieee"
    supported_templates: list[str] = Field(default_factory=lambda: ["ieee", "acm"])

    @model_validator(mode="after")
    def validate_default_template(self) -> "OutputSettings":
        if self.default_template not in self.supported_templates:
            raise ValueError("default_template must exist in supported_templates")
        return self


class RetrievalSettings(BaseModel):
    web_provider: str = "scrape"
    paper_providers: list[str] = Field(default_factory=lambda: ["arxiv", "semantic_scholar"])
    allow_metadata_fallback: bool = True
    metadata_fallback_confidence_penalty: float = Field(default=0.15, ge=0, le=1)

    @field_validator("paper_providers")
    @classmethod
    def validate_paper_providers(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("paper_providers cannot be empty")
        return value

    @field_validator("web_provider")
    @classmethod
    def validate_web_provider(cls, value: str) -> str:
        supported = {"tavily", "browser_use", "hybrid", "scrape"}
        if value not in supported:
            raise ValueError(f"web_provider must be one of: {sorted(supported)}")
        return value


class AppSettings(BaseModel):
    runtime: RuntimeSettings
    models: ModelSettings
    output: OutputSettings
    retrieval: RetrievalSettings
