"""Approval decision types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ApprovalGate(StrEnum):
    SCOPE = "scope"
    RESEARCH_PLAN = "research_plan"
    EVIDENCE_OUTLINE = "evidence_outline"
    RECOMMENDATION = "recommendation"


class ApprovalDecision(BaseModel):
    """A human approval decision at a gate."""

    approval_id: str
    run_id: str
    gate: ApprovalGate
    decision: str  # approved, rejected, revision_requested
    rationale: str = ""
    approver_id: str = ""
    decided_at: datetime = Field(default_factory=datetime.now)
