"""Report outline types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas.scope import SourceMix


class SectionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DRAFTED = "drafted"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    REPAIRING = "repairing"


class OutlineSection(BaseModel):
    """A section in the report outline."""

    section_id: str
    title: str
    purpose: str = ""
    parent_id: str | None = None
    required_claim_ids: list[str] = Field(default_factory=list)
    unresolved_question_ids: list[str] = Field(default_factory=list)
    minimum_evidence_requirements: SourceMix = Field(default_factory=SourceMix)
    status: SectionStatus = SectionStatus.PENDING


class Outline(BaseModel):
    """A versioned report outline."""

    outline_id: str
    run_id: str
    version: int = 1
    sections: list[OutlineSection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
