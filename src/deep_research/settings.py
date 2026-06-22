"""Application settings for Deep Research Assistant.

Configuration is loaded from environment variables with a DEEP_RESEARCH_ prefix.
Supports .env file loading for local development.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Configuration for a single model tier."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_MODEL_")

    provider: str = "google"
    model: str = "gemini-3-flash-preview"

    @property
    def model_id(self) -> str:
        """Return the fully qualified model identifier."""
        if self.model:
            return self.model
        return f"{self.provider}/default"


class ModelRoutingConfig(BaseSettings):
    """Model routing configuration for the three tiers."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_MODELS_")

    fast: ModelConfig = Field(default_factory=ModelConfig)
    reasoning: ModelConfig = Field(default_factory=ModelConfig)
    verification: ModelConfig = Field(default_factory=ModelConfig)


class BudgetConfig(BaseSettings):
    """Default research budget constraints."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_BUDGET_")

    searches: int = 80
    opened_sources: int = 50
    tokens: int = 120_000
    sources_per_perspective: int = 12
    maximum_cost: float = 25.0
    maximum_wall_time_seconds: int = 1800


class ApprovalConfig(BaseSettings):
    """Approval gate configuration."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_APPROVALS_")

    scope_required_for_risk: Literal["high", "medium", "all", "never"] = "high"
    plan_required_for_risk: Literal["high", "medium", "all", "never"] = "high"
    outline_required_for_risk: Literal["high", "medium", "all", "never"] = "high"
    publication_required_for_external: bool = True
    mode: Literal["strict", "auto_approve"] = "strict"


class ResearchPolicyConfig(BaseSettings):
    """Research quality and policy defaults."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_POLICY_")

    minimum_primary_source_ratio: float = 0.5
    required_counter_search_materiality: Literal["low", "medium", "high"] = "high"
    maximum_source_age_days: int | None = None
    require_source_snapshots: bool = True
    allow_vendor_sources: bool = True
    vendor_claims_require_independent_support: bool = True


class WorkflowConfig(BaseSettings):
    """Workflow execution settings."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_WORKFLOW_")

    version: str = "1.0.0"
    maximum_parallel_questions: int = 3
    checkpoint_after_each_batch: bool = True
    verification_repair_limit: int = 2
    enable_iterative_research: bool = True
    enable_follow_up_questions: bool = True
    max_cycles: int = 10
    low_information_gain_cycle_threshold: int = 3
    information_gain_floor: float = 0.05
    llm_timeout_seconds: int = 45
    retry_limit: int = 2


class SchedulerConfig(BaseSettings):
    """Priority weighting for research frontier scheduling."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_SCHEDULER_")

    w_materiality: float = 0.3
    w_risk: float = 0.2
    w_dependency: float = 0.15
    w_uncertainty: float = 0.2
    w_novelty: float = 0.1
    w_cost: float = 0.05


class InformationGainConfig(BaseSettings):
    """Weights for iterative information-gain scoring."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_INFORMATION_GAIN_")

    alpha_novel_claims: float = 0.3
    beta_novel_evidence: float = 0.25
    gamma_resolved_gaps: float = 0.25
    delta_resolved_contradictions: float = 0.15
    lambda_duplication: float = 0.05


class PerspectiveBudgetConfig(BaseSettings):
    """Default per-perspective budget allocations."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_PERSPECTIVE_BUDGET_")

    searches: int = 12
    tokens: int = 18_000
    sources: int = 8


class SecurityConfig(BaseSettings):
    """Security enforcement settings."""

    model_config = SettingsConfigDict(env_prefix="DEEP_RESEARCH_SECURITY_")

    enforce_identity_propagation: bool = True
    require_confirmation_for_writes: bool = True
    quarantine_untrusted_instructions: bool = True


class Settings(BaseSettings):
    """Root settings for Deep Research Assistant."""

    model_config = SettingsConfigDict(
        env_prefix="DEEP_RESEARCH_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application identity
    name: str = "deep-research-assistant"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///deep_research.db",
        description="SQLAlchemy async database URL",
    )

    # Paths
    artifact_dir: Path = Field(
        default=Path("./artifacts"),
        description="Directory for generated artifacts (reports, snapshots)",
    )
    source_snapshot_dir: Path = Field(
        default=Path("./snapshots"),
        description="Directory for cached source snapshots",
    )

    # Sub-configurations
    models: ModelRoutingConfig = Field(default_factory=ModelRoutingConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    information_gain: InformationGainConfig = Field(default_factory=InformationGainConfig)
    perspective_budget: PerspectiveBudgetConfig = Field(default_factory=PerspectiveBudgetConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    research_policy: ResearchPolicyConfig = Field(default_factory=ResearchPolicyConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    approvals: ApprovalConfig = Field(default_factory=ApprovalConfig)

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_reload: bool = False

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    log_file_path: Path = Field(
        default=Path("./artifacts/logs/deep_research.log"),
        description="Path to the JSONL application log file.",
    )

    # External APIs
    exa_api_key: str | None = None


def get_settings() -> Settings:
    """Return cached settings instance.

    Uses a module-level singleton to avoid re-parsing env vars on every call.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


_settings: Settings | None = None
