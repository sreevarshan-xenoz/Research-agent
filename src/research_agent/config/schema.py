from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, model_serializer, SecretStr


class RuntimeSettings(BaseModel):
    """Runtime configuration for research agent execution."""
    mode: Literal["api_only", "parallel", "async"] = "parallel"
    max_iterations: int = Field(default=4, ge=1, le=20)
    max_runtime_minutes: int = Field(default=25, ge=1)
    max_cost_usd: float = Field(default=5.0, ge=0)
    parallel_workers: int = Field(default=4, ge=1, le=8, description="Max concurrent subagent workers")
    interactive_checkpoints: bool = Field(default=False, description="Pause graph execution at boundaries to wait for human-in-the-loop input")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        supported = {"api_only", "parallel", "async"}
        if value not in supported:
            raise ValueError(f"mode must be one of: {sorted(supported)}")
        return value


class OpenAISettings(BaseModel):
    """OpenAI-specific configuration."""
    api_key: SecretStr = SecretStr("")
    api_base: str | None = Field(default=None, description="Custom API base URL (e.g., for Azure OpenAI or proxies)")
    organization: str | None = Field(default=None, description="OpenAI organization ID")
    timeout_seconds: int = Field(default=60, ge=10, le=300)


class AnthropicSettings(BaseModel):
    """Anthropic-specific configuration."""
    api_key: SecretStr = SecretStr("")
    api_base: str | None = Field(default=None, description="Custom API base URL")
    timeout_seconds: int = Field(default=60, ge=10, le=300)


class GeminiSettings(BaseModel):
    """Google Gemini-specific configuration."""
    api_key: SecretStr = SecretStr("")
    api_base: str | None = Field(default=None, description="Custom API base URL (e.g., for Vertex AI)")
    timeout_seconds: int = Field(default=60, ge=10, le=300)


class GroqSettings(BaseModel):
    """Groq-specific configuration (ultra-fast inference)."""
    api_key: SecretStr = SecretStr("")
    api_base: str | None = Field(default=None, description="Custom API base URL")
    timeout_seconds: int = Field(default=30, ge=10, le=300)


class CodeSandboxSettings(BaseModel):
    """Configuration for the Verified Code Execution Sandbox (P24)."""
    enabled: bool = True
    container_timeout: int = Field(default=60, ge=10, le=600, description="Max seconds per code execution")
    memory_limit_mb: int = Field(default=512, ge=64, le=8192, description="Memory limit per container")
    max_output_chars: int = Field(default=100_000, ge=1_000, le=1_000_000, description="Max chars to capture from stdout/stderr")
    pool_size: int = Field(default=2, ge=0, le=10, description="Number of warm containers to prewarm")
    min_verification_potential: float = Field(default=0.3, ge=0.0, le=1.0, description="Min verification potential threshold")
    claim_extraction_enabled: bool = True
    code_generation_enabled: bool = True
    r_support: bool = Field(default=False, description="Enable R language support")
    julia_support: bool = Field(default=False, description="Enable Julia language support")


class DeepResearchSettings(BaseModel):
    """Configuration for the Agentic Deep Research Engine (P21)."""
    enabled: bool = True
    max_search_rounds: int = Field(default=3, ge=1, le=10, description="Maximum search rounds per task")
    max_citation_chain_depth: int = Field(default=2, ge=0, le=5, description="Max recursion depth for citation chaining")
    max_chained_papers: int = Field(default=15, ge=1, le=100, description="Max total chained papers per run")
    max_seed_papers: int = Field(default=3, ge=1, le=20, description="Max seed papers to chain from per task")
    min_relevance_threshold: float = Field(default=0.15, ge=0.0, le=1.0, description="Min relevance for chaining a paper")
    novelty_decay_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="Novelty ratio below which search terminates")
    score_plateau_threshold: float = Field(default=0.05, ge=0.0, le=1.0, description="Min score improvement to continue")
    max_stalled_rounds: int = Field(default=2, ge=1, le=5, description="Max rounds below plateau threshold before termination")


class ModelRouterTaskConfig(BaseModel):
    """Configuration for a single task type in the model router."""
    provider: str = "ollama"
    model: str = Field(default="", description="Full model name (e.g. openai/gpt-4o). If empty, inferred from provider + models section.")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)


class ModelRouterSettings(BaseModel):
    """Task-to-model routing configuration.

    Maps each research task type to a specific model/provider combination.
    Task types: plan, write, critique, code, embed, search, evaluate
    """
    enabled: bool = True
    default_provider: str = "ollama"
    default_model: str = Field(default="", description="Fallback model when no task-specific mapping exists")
    tasks: dict[str, ModelRouterTaskConfig] = Field(
        default_factory=lambda: {
            "plan": ModelRouterTaskConfig(provider="gemini", model="gemini/gemini-2.0-flash"),
            "write": ModelRouterTaskConfig(provider="groq", model="groq/llama-3.3-70b-versatile"),
            "critique": ModelRouterTaskConfig(provider="ollama", model="ollama/deepseek-r1:8b"),
            "code": ModelRouterTaskConfig(provider="gemini", model="gemini/gemini-2.0-flash"),
            "embed": ModelRouterTaskConfig(provider="ollama", model="ollama/nomic-embed-text"),
        }
    )


class ModelSettings(BaseModel):
    """Model configuration with multi-provider support.

    Role definitions:
    - orchestrator: Local model for planning, clarification, critic. Default: ollama/qwen3:8b
    - subagent: Model for section synthesis (auto-selects from local/cloud/fallback)
    - provider_priority: Order of providers to try (ollama > openrouter > puter > nvidia > openai > anthropic)
    """
    # Orchestrator (head) model
    orchestrator_model: str = "ollama/qwen3:8b"
    orchestrator_provider: Literal["ollama", "openrouter", "vllm", "openai", "anthropic", "gemini", "groq"] = "ollama"

    # Subagent model settings
    subagent_provider: Literal["auto", "ollama", "openrouter", "puter", "nvidia", "vllm", "openai", "anthropic", "gemini", "groq"] = "auto"
    subagent_local: str = "deepseek-r1:8b"
    subagent_cloud: str = "openrouter/free"
    subagent_nvidia: str = "nvidia/meta/llama-3.1-405b-instruct"
    subagent_vllm: str = "deepseek-r1"
    subagent_openai: str = "openai/gpt-4o"
    subagent_anthropic: str = "anthropic/claude-3-5-sonnet-20241022"
    subagent_gemini: str = "gemini/gemini-2.0-flash"
    subagent_groq: str = "groq/llama-3.3-70b-versatile"

    # Provider priority
    provider_priority: list[str] = Field(
        default_factory=lambda: ["ollama", "openrouter", "puter", "nvidia", "vllm", "openai", "anthropic", "gemini", "groq"]
    )

    # Legacy aliases (deprecated, for backward compatibility)
    head_model: str = ""
    subagent_model: str = ""
    worker_model: str = ""
    strong_model: str = ""

    @model_validator(mode="after")
    def populate_legacy_aliases(self) -> "ModelSettings":
        if not self.head_model:
            self.head_model = self.orchestrator_model
        if not self.subagent_model:
            self.subagent_model = self.subagent_cloud
        if not self.worker_model:
            self.worker_model = self.subagent_local
        if not self.strong_model:
            self.strong_model = self.subagent_cloud
        return self

    @field_validator("provider_priority", mode="before")
    @classmethod
    def validate_provider_priority(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, list):
            raise ValueError("provider_priority must be a list or a comma-separated string")
        supported = {"ollama", "openrouter", "puter", "nvidia", "vllm", "openai", "anthropic", "gemini", "groq"}
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
    default_acm_layout: str = Field(default="sigconf", description="Default ACM layout (e.g., sigconf or manuscript)")

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
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex", "pubmed"]
    )
    max_papers_per_section: int = Field(default=15, ge=1, le=50)
    chunk_size: int = Field(default=1024, ge=256, le=4096)
    chunk_overlap: int = Field(default=128, ge=0, le=512)
    allow_metadata_fallback: bool = True
    metadata_fallback_confidence_penalty: float = Field(default=0.15, ge=0, le=1)
    enable_fuzzy_dedup: bool = True
    embedding_model: str = Field(default="intfloat/multilingual-e5-large", description="Model for multilingual embeddings")

    @field_validator("paper_providers")
    @classmethod
    def validate_paper_providers(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("paper_providers cannot be empty")
        supported = {"arxiv", "semantic_scholar", "openalex", "pubmed", "github", "patent", "news_social"}
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
    api_key: SecretStr = SecretStr("")
    timeout_seconds: int = Field(default=60, ge=10, le=180)


class RedisSettings(BaseModel):
    """Redis connection settings."""
    url: str = "redis://localhost:6379"
    max_connections: int = Field(default=10, ge=1)
    timeout_seconds: int = Field(default=5, ge=1)


class VllmSettings(BaseModel):
    """vLLM configuration."""
    api_base: str = "http://localhost:8000/v1"
    api_key: SecretStr = SecretStr("")
    model: str = "deepseek-r1"
    timeout_seconds: int = Field(default=120, ge=30, le=300)


class QdrantSettings(BaseModel):
    """Qdrant vector database configuration."""
    location: str = ".runtime/qdrant"
    grpc_port: int = Field(default=6334, ge=1, le=65535)
    prefer_grpc: bool = True


class AuthSettings(BaseModel):
    """Authentication settings."""
    secret_key: SecretStr = SecretStr("DEV_SECRET_DO_NOT_USE_IN_PROD")
    jwt_lifetime_seconds: int = 3600
    enable_registration: bool = True


class WatchdogEmailSettings(BaseModel):
    """SMTP/email configuration for watchdog digest notifications."""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    from_email: str = "noreply@research-agent.local"
    from_name: str = "Research Watchdog"


class FeatureFlags(BaseModel):
    """Feature flags for v2 features."""
    parallel_subagents: bool = True
    cite_autofix: bool = True
    session_persistence: Literal["localStorage", "redis", "none"] = "localStorage"
    enable_session_persistence: bool = True
    pdf_export: bool = True
    multi_language: bool = False
    survey_generator: bool = True
    plagiarism_check: bool = True
    research_watchdog: bool = True
    overleaf_integration: bool = True
    literature_monitoring: bool = True


class ObservabilitySettings(BaseModel):
    """Observability and monitoring configuration."""
    enable_tracing: bool = False
    enable_metrics: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


    @model_serializer(mode="wrap")
    def _serialize_safe(self, handler) -> dict:
        """Serialize settings with secrets masked for debug dumps and logging."""
        raw = handler(self)
        # Mask known secret fields in the serialized output
        for section in ("auth", "openrouter", "vllm"):
            if section in raw and isinstance(raw[section], dict):
                for key in ("secret_key", "api_key"):
                    if key in raw[section]:
                        raw[section][key] = "***MASKED***"
        return raw


class AppSettings(BaseModel):
    """Main application settings."""
    version: str = "2.0"
    runtime: RuntimeSettings
    models: ModelSettings
    model_router: ModelRouterSettings = Field(default_factory=ModelRouterSettings)
    output: OutputSettings
    retrieval: RetrievalSettings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    groq: GroqSettings = Field(default_factory=GroqSettings)
    vllm: VllmSettings = Field(default_factory=VllmSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    watchdog_email: WatchdogEmailSettings = Field(default_factory=WatchdogEmailSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    deep_research: DeepResearchSettings = Field(default_factory=DeepResearchSettings)
    code_sandbox: CodeSandboxSettings = Field(default_factory=CodeSandboxSettings)
