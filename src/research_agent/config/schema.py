from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, SecretStr


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


class EnsembleSettings(BaseModel):
    """Multi-Model Ensemble Voting configuration (P31).

    Controls which tasks use ensemble voting, how many models to query,
    which voting strategy to use, and per-model timeouts.
    """
    enabled: bool = True
    # Default ensemble config for all tasks
    default_num_models: int = Field(default=3, ge=1, le=8, description="Default number of models per ensemble round")
    default_timeout_s: float = Field(default=30.0, ge=5.0, le=120.0, description="Default timeout per model call")
    min_success_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum fraction of models that must succeed")
    # Per-task overrides: task_type -> {strategy, num_models, timeout_s}
    task_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "critic": {"strategy": "weighted", "num_models": 3, "timeout_s": 30.0},
            "planner": {"strategy": "majority", "num_models": 2, "timeout_s": 30.0},
            "composer": {"strategy": "consensus", "num_models": 3, "timeout_s": 60.0},
            "bias_detection": {"strategy": "majority", "num_models": 3, "timeout_s": 30.0},
            "hallucination_guard": {"strategy": "weighted", "num_models": 3, "timeout_s": 30.0},
        }
    )


class JobQueueSettings(BaseModel):
    """Configuration for the async job queue (P16)."""
    enabled: bool = True
    worker_count: int = Field(default=1, ge=0, le=16, description="Number of worker processes")
    poll_interval: float = Field(default=1.0, ge=0.1, le=10.0, description="Seconds between queue polls")
    max_concurrent_per_user: int = Field(default=3, ge=1, le=20, description="Max concurrent research runs per user")
    default_timeout: int = Field(default=600, ge=60, le=3600, description="Default job timeout in seconds")
    max_retries: int = Field(default=2, ge=0, le=10, description="Max retries for failed jobs")


class MultiModalSettings(BaseModel):
    """Configuration for Multi-Modal Paper Analysis (P22).

    Controls figure extraction, table parsing, equation extraction,
    chart-to-text generation, and multi-modal Q&A capabilities.
    """
    enabled: bool = True
    extract_figures: bool = Field(default=True, description="Extract embedded images from PDFs")
    extract_tables: bool = Field(default=True, description="Extract tables via pdfplumber visual detection")
    extract_equations: bool = Field(default=True, description="Extract LaTeX equations via Pix2Text/regex")
    generate_chart_descriptions: bool = Field(default=True, description="Generate accessibility descriptions for charts")
    max_figures: int = Field(default=20, ge=1, le=100)
    max_tables: int = Field(default=30, ge=1, le=100)
    max_equations: int = Field(default=50, ge=1, le=200)
    pix2text_enabled: bool = Field(default=True, description="Attempt Pix2Text OCR-based equation extraction")


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


class RBACSettings(BaseModel):
    """Role-based access control settings (P18)."""
    enabled: bool = True
    default_role: str = "viewer"  # Default role for new users
    allow_self_role_upgrade: bool = Field(default=False, description="If True, users can upgrade their own role (dev only)")


class RateLimitSettings(BaseModel):
    """API rate limiting configuration (P18)."""
    enabled: bool = True
    default_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    authenticated_requests_per_minute: int = Field(default=300, ge=1, le=10000)
    admin_requests_per_minute: int = Field(default=1000, ge=1, le=10000)
    burst_size: int = Field(default=20, ge=1, le=200)
    # Per-endpoint overrides (endpoint_path -> limit)
    endpoint_overrides: dict[str, int] = Field(default_factory=dict)


class AuditSettings(BaseModel):
    """Audit logging configuration (P18)."""
    enabled: bool = True
    log_request_body: bool = Field(default=False, description="Log full request bodies (may contain PII)")
    log_response_status: bool = True
    retention_days: int = Field(default=90, ge=1, le=365)
    # Paths to exclude from audit logging (e.g. /health, /metrics)
    exclude_paths: list[str] = Field(default_factory=lambda: ["/health", "/metrics", "/api/health"])


class SSOSettings(BaseModel):
    """SSO/OAuth provider settings (P18)."""
    google_client_id: str = Field(default="", description="Google OAuth2 client ID")
    google_client_secret: SecretStr = SecretStr("")
    github_client_id: str = Field(default="", description="GitHub OAuth2 client ID")
    github_client_secret: SecretStr = SecretStr("")
    orcid_client_id: str = Field(default="", description="ORCID OAuth2 client ID")
    orcid_client_secret: SecretStr = SecretStr("")
    enabled: bool = False
    allow_registration_via_sso: bool = True


class SecretsSettings(BaseModel):
    """Secrets management / encryption settings (P18)."""
    encryption_key: SecretStr = SecretStr("")  # Fernet key for encrypting stored API keys
    key_rotation_days: int = Field(default=90, ge=1, le=365)
    encrypt_api_keys_at_rest: bool = Field(default=True)


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
    """Observability and monitoring configuration (P17).

    Controls Prometheus metrics, JSON structured logging,
    OpenTelemetry tracing, and Sentry error tracking.
    """
    # General
    enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    json_logging: bool = Field(default=False, description="Enable JSON structured log output (instead of plain text)")

    # Prometheus metrics
    enable_metrics: bool = True
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Port for Prometheus /metrics HTTP server")
    metrics_path: str = Field(default="/metrics", description="Path for Prometheus metrics endpoint")

    # OpenTelemetry tracing
    enable_tracing: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otlp_endpoint: str = Field(default="", description="OTLP HTTP exporter endpoint (e.g., http://localhost:4318/v1/traces)")
    otlp_console_export: bool = Field(default=False, description="Also export spans to console for debugging")
    tracer_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Tracing sample rate (0.0-1.0)")

    # Sentry error tracking
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking. Empty = disabled")
    sentry_environment: str = Field(default="development", description="Environment tag for Sentry")
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Sentry performance tracing sample rate")




class TemplateLibrarySettings(BaseModel):
    """Configuration for Research Templates & Presets (P39).

    Controls the template library, conference presets, and custom template storage.
    """
    enabled: bool = True
    default_template_id: str = Field(default="standard", description="Default research template ID")
    default_preset_id: str = Field(default="", description="Default conference preset ID")
    store_path: str = Field(default=".runtime/templates.json", description="Path for custom template persistence")


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
    rbac: RBACSettings = Field(default_factory=RBACSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    sso: SSOSettings = Field(default_factory=SSOSettings)
    secrets_mgmt: SecretsSettings = Field(default_factory=SecretsSettings)
    watchdog_email: WatchdogEmailSettings = Field(default_factory=WatchdogEmailSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    deep_research: DeepResearchSettings = Field(default_factory=DeepResearchSettings)
    code_sandbox: CodeSandboxSettings = Field(default_factory=CodeSandboxSettings)
    job_queue: JobQueueSettings = Field(default_factory=JobQueueSettings)
    ensemble: EnsembleSettings = Field(default_factory=EnsembleSettings)
    multi_modal: MultiModalSettings = Field(default_factory=MultiModalSettings)
    template_library: TemplateLibrarySettings = Field(default_factory=TemplateLibrarySettings)
