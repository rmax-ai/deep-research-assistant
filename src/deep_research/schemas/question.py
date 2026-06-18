"""Research question graph types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class QuestionType(StrEnum):
    DEFINITIONAL = "definitional"
    DESCRIPTIVE = "descriptive"
    MECHANISTIC = "mechanistic"
    COMPARATIVE = "comparative"
    HISTORICAL = "historical"
    CAUSAL = "causal"
    NORMATIVE = "normative"
    QUANTITATIVE = "quantitative"
    IMPLEMENTATION = "implementation"
    SECURITY = "security"
    FAILURE_MODE = "failure_mode"
    COUNTERFACTUAL = "counterfactual"
    EVIDENCE_CHALLENGE = "evidence_challenge"
    CONTRADICTION_RESOLUTION = "contradiction_resolution"


class QuestionOrigin(StrEnum):
    SYSTEM_GENERATED = "system_generated"
    USER_SUBMITTED = "user_submitted"
    EVIDENCE_CONDITIONED = "evidence_conditioned"
    MODERATOR_INTRODUCED = "moderator_introduced"
    CONTRADICTION_TRIGGERED = "contradiction_triggered"


class QuestionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    BLOCKED = "blocked"
    DEPRIORITIZED = "deprioritized"
    REOPENED = "reopened"


class ResearchQuestion(BaseModel):
    """A first-class research question in the question graph."""

    question_id: str
    text: str
    question_type: QuestionType
    perspective_id: str | None = None
    parent_question_ids: list[str] = Field(default_factory=list)
    child_question_ids: list[str] = Field(default_factory=list)
    origin: QuestionOrigin = QuestionOrigin.SYSTEM_GENERATED
    rationale: str = ""
    priority: float = 0.5
    novelty_score: float = 0.5
    risk_score: float = 0.0
    status: QuestionStatus = QuestionStatus.PENDING
    resolution_summary: str | None = None
    linked_claim_ids: list[str] = Field(default_factory=list)
    linked_query_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QuestionEdge(BaseModel):
    """An edge in the question graph representing a dependency."""

    parent_id: str
    child_id: str
    edge_type: str = "requires"  # requires, refines, contradicts


class QuestionGraph(BaseModel):
    """The full question graph for a research run."""

    run_id: str
    questions: dict[str, ResearchQuestion] = Field(default_factory=dict)
    edges: list[QuestionEdge] = Field(default_factory=list)
    version: int = 1
