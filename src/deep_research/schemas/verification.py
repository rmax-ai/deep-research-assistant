"""Verification finding types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas._time import utc_now


class VerificationSeverity(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    MINOR = "minor"
    STYLISTIC = "stylistic"


class VerificationFinding(BaseModel):
    """A finding from the independent verification pass."""

    finding_id: str
    severity: VerificationSeverity
    description: str
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_section_ids: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None
    verifier_model: str = ""
    found_at: datetime = Field(default_factory=utc_now)


class VerificationReport(BaseModel):
    """Complete verification report for a draft."""

    run_id: str
    draft_version: int
    findings: list[VerificationFinding] = Field(default_factory=list)
    blocking_count: int = 0
    passed: bool = False
    verified_at: datetime = Field(default_factory=utc_now)
