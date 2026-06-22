"""Core research run types and enums."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    pass  # ResearchScope imported at runtime via string annotation


def _utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class RunStatus(StrEnum):
    """Lifecycle status of a research run."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    SCOPE_PROPOSED = "scope_proposed"
    PLAN_PROPOSED = "plan_proposed"
    RESEARCHING = "researching"
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    VERIFYING = "verifying"
    AWAITING_APPROVAL = "awaiting_approval"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class ResearchMode(StrEnum):
    """Operating mode for a research run."""

    AUTONOMOUS = "autonomous"
    COLLABORATIVE = "collaborative"
    REVIEW_FIRST = "review_first"
    CONTINUOUS_WATCH = "continuous_watch"


class OutputType(StrEnum):
    """Desired output format."""

    TECHNICAL_REPORT = "technical_report"
    EXECUTIVE_BRIEF = "executive_brief"
    ARCHITECTURE_DECISION_RECORD = "architecture_decision_record"
    EVIDENCE_MAP = "evidence_map"
    COMPARISON_MATRIX = "comparison_matrix"
    RISK_MEMO = "risk_memo"
    SOURCE_BIBLIOGRAPHY = "source_bibliography"
    RESEARCH_DOSSIER = "research_dossier"


class DepthLevel(StrEnum):
    """Desired research depth."""

    OVERVIEW = "overview"
    STANDARD = "standard"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


class ResearchObjective(BaseModel):
    """The user's research request, structured."""

    model_config = ConfigDict(frozen=True)

    title: str
    primary_question: str
    decision_to_support: str | None = None
    intended_audience: list[str] = Field(default_factory=list)
    output_type: OutputType = OutputType.TECHNICAL_REPORT
    desired_depth: DepthLevel = DepthLevel.STANDARD
    deadline: datetime | None = None
    language: str = "en"


class ResearchBudget(BaseModel):
    """Resource budget for a research run."""

    max_wall_time_seconds: int = 1800
    max_model_tokens: int = 1_000_000
    max_searches: int = 80
    max_opened_sources: int = 50
    max_cost_currency: float = 25.0
    max_parallel_branches: int = 6
    max_questions: int = 200
    minimum_primary_source_ratio: float = 0.5
    minimum_independent_source_clusters: int = 2


class ResearchRun(BaseModel):
    """Top-level durable aggregate for a research investigation."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    tenant_id: str = "default"
    user_id: str
    objective: ResearchObjective
    status: RunStatus = RunStatus.DRAFT
    mode: ResearchMode = ResearchMode.REVIEW_FIRST
    policy_profile_id: str = "default"
    workflow_version: str = "1.0.0"
    model_routing_profile_id: str = "default"
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    scope: "ResearchScope | None" = None  # type: ignore[name-defined]
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
