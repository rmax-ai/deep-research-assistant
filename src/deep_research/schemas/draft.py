"""Section draft types."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MissingClaim(BaseModel):
    """A claim that the section writer needs but doesn't have."""

    description: str
    recommended_question: str


class SectionDraft(BaseModel):
    """A generated section draft."""

    section_id: str
    content: str = ""
    status: str = "draft"  # draft, blocked, verified, repaired
    blocked_reason: str | None = None
    missing_claims: list[MissingClaim] = Field(default_factory=list)
    model_id: str = ""
    prompt_version: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
