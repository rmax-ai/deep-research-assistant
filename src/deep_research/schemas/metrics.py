"""Research metrics and stopping decision types."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from deep_research.schemas._time import utc_now


class StoppingDecision(BaseModel):
    """Result of stopping condition evaluation."""

    should_stop: bool = False
    reasons: list[str] = Field(default_factory=list)
    unresolved_material_questions: list[str] = Field(default_factory=list)
    marginal_information_gain: float = 0.0
    evidence_diversity_score: float = 0.0
    primary_source_coverage: float = 0.0
    contradiction_resolution_rate: float = 0.0
    budget_remaining: dict[str, float] = Field(default_factory=dict)


class ResearchMetrics(BaseModel):
    """Aggregate metrics for a research run."""

    total_questions: int = 0
    resolved_questions: int = 0
    total_sources_retrieved: int = 0
    accepted_sources: int = 0
    rejected_sources: int = 0
    primary_source_ratio: float = 0.0
    total_evidence_fragments: int = 0
    total_claims: int = 0
    unsupported_claim_count: int = 0
    disputed_claim_count: int = 0
    total_contradictions: int = 0
    resolved_contradictions: int = 0
    total_model_tokens: int = 0
    total_cost: float = 0.0
    total_wall_time_seconds: float = 0.0
    human_interventions: int = 0
    updated_at: datetime = Field(default_factory=utc_now)
