"""Contradiction tracking types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas.claim import Materiality


class ContradictionType(StrEnum):
    DIRECT_FACTUAL_CONFLICT = "direct_factual_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    DEFINITIONAL_CONFLICT = "definitional_conflict"
    SCOPE_MISMATCH = "scope_mismatch"
    METHODOLOGICAL_DISAGREEMENT = "methodological_disagreement"
    CAUSAL_DISAGREEMENT = "causal_disagreement"
    INTERPRETATION_DISAGREEMENT = "interpretation_disagreement"
    SOURCE_SUPERSESSION = "source_supersession"


class ResolutionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED_IN_FAVOR = "resolved_in_favor"  # one claim preferred
    RESOLVED_SYNTHESIS = "resolved_synthesis"  # both partially correct
    RESOLVED_CONTEXTUAL = "resolved_contextual"  # depends on context
    ACKNOWLEDGED = "acknowledged"  # cannot resolve, documented
    SUPERSEDED = "superseded"  # newer evidence resolved it


class Contradiction(BaseModel):
    """A detected contradiction between claims or sources."""

    contradiction_id: str
    claim_ids: list[str] = Field(default_factory=list)
    contradiction_type: ContradictionType = ContradictionType.DIRECT_FACTUAL_CONFLICT
    explanation: str = ""
    possible_resolution: str | None = None
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    materiality: Materiality = Materiality.MEDIUM
    detected_at: datetime = Field(default_factory=datetime.utcnow)
