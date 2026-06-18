"""Claim and inference types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ClaimType(StrEnum):
    FACTUAL = "factual"
    DEFINITIONAL = "definitional"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    PREDICTIVE = "predictive"
    RECOMMENDATION = "recommendation"
    INTERPRETATION = "interpretation"


class EpistemicStatus(StrEnum):
    SOURCE_STATED = "source_stated"
    DIRECTLY_OBSERVED = "directly_observed"
    EXTRACTED = "extracted"
    CORROBORATED = "corroborated"
    INFERRED = "inferred"
    CAUSAL_INFERENCE = "causal_inference"
    DISPUTED = "disputed"
    SPECULATIVE = "speculative"
    RECOMMENDATION = "recommendation"
    UNRESOLVED = "unresolved"


class Materiality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class InferenceOperation(StrEnum):
    DEDUCTION = "deduction"
    INDUCTION = "induction"
    ABDUCTION = "abduction"
    ANALOGY = "analogy"
    CAUSAL_REASONING = "causal_reasoning"
    SYNTHESIS = "synthesis"
    GENERALIZATION = "generalization"


class InferenceStep(BaseModel):
    """A single reasoning step in a chain of inferences."""

    premise_claim_ids: list[str] = Field(default_factory=list)
    operation: InferenceOperation
    conclusion_claim_id: str = ""
    rationale: str = ""
    model_id: str = ""
    prompt_version: str = ""
    verifier_status: ReviewStatus = ReviewStatus.UNREVIEWED


class Claim(BaseModel):
    """An atomic, evidence-backed claim."""

    claim_id: str
    text: str
    atomic_form: str = ""
    claim_type: ClaimType = ClaimType.FACTUAL
    epistemic_status: EpistemicStatus = EpistemicStatus.EXTRACTED
    evidence_ids: list[str] = Field(default_factory=list)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    inference_steps: list[InferenceStep] = Field(default_factory=list)
    qualifiers: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    materiality: Materiality = Materiality.MEDIUM
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    owner_agent: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
