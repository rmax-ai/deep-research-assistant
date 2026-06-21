"""Search planning and query definitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas._time import utc_now
from deep_research.schemas.scope import SourceMix


class FreshnessRequirement(StrEnum):
    ANY = "any"
    LAST_YEAR = "last_year"
    LAST_SIX_MONTHS = "last_six_months"
    LAST_MONTH = "last_month"
    LAST_WEEK = "last_week"


class StopCondition(BaseModel):
    """A condition that, when met, stops search for a question."""

    condition_type: str  # e.g., "min_sources", "min_primary", "info_gain_threshold"
    threshold: float
    met: bool = False


class SearchQuery(BaseModel):
    """A single search query within a search plan."""

    query_id: str
    raw_query: str
    rewritten_query: str | None = None
    strategy: str = "exact"  # exact, synonym, official_docs, standards, etc.
    provider: str = "web_search"
    max_results: int = 10
    executed_at: datetime | None = None


class SearchPlan(BaseModel):
    """A complete search plan for one research question."""

    question_id: str
    objective: str
    queries: list[SearchQuery] = Field(default_factory=list)
    required_source_mix: SourceMix = Field(default_factory=SourceMix)
    exclusion_rules: list[str] = Field(default_factory=list)
    freshness_requirement: FreshnessRequirement = FreshnessRequirement.ANY
    max_results: int = 50
    max_pages: int = 20
    stop_conditions: list[StopCondition] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
