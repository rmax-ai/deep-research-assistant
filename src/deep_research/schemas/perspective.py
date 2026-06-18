"""Research perspectives — lenses through which a topic is investigated."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from deep_research.schemas.scope import SourceType


class PerspectiveStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DEPLETED = "depleted"
    PAUSED = "paused"


class Perspective(BaseModel):
    """A research policy / lens, not just a role prompt."""

    model_config = ConfigDict(frozen=True)

    perspective_id: str
    name: str
    purpose: str
    required_questions: list[str] = Field(default_factory=list)
    preferred_source_types: list[SourceType] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    budget_weight: float = 1.0
    status: PerspectiveStatus = PerspectiveStatus.ACTIVE
