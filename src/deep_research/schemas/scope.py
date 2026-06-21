"""Research scope and constraints."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from deep_research.schemas._time import utc_now


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(StrEnum):
    OFFICIAL_DOCUMENTATION = "official_documentation"
    STANDARD = "standard"
    ACADEMIC_PAPER = "academic_paper"
    TECHNICAL_BLOG = "technical_blog"
    REPOSITORY = "repository"
    ISSUE_TRACKER = "issue_tracker"
    VENDOR_WHITEPAPER = "vendor_whitepaper"
    NEWS_ARTICLE = "news_article"
    INCIDENT_REPORT = "incident_report"
    REGULATORY_FILING = "regulatory_filing"
    EXPERT_INTERVIEW = "expert_interview"
    OTHER = "other"


class SourceMix(BaseModel):
    """Required mix of source types."""

    minimum_primary: int = 2
    minimum_standards: int = 0
    minimum_academic: int = 0
    minimum_independent: int = 1
    allowed_types: list[SourceType] = Field(default_factory=lambda: list(SourceType))


class SourceConstraints(BaseModel):
    """Constraints on which sources may be used."""

    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    required_source_mix: SourceMix = Field(default_factory=SourceMix)
    require_snapshots: bool = True
    maximum_source_age_days: int | None = None
    allow_vendor_sources: bool = True
    vendor_claims_require_independent: bool = True


class TimeRange(BaseModel):
    """A temporal window."""

    start: date | None = None
    end: date | None = None


class Definition(BaseModel):
    """A scoped term definition."""

    term: str
    definition: str
    source: str | None = None


class Assumption(BaseModel):
    """An explicit assumption made during research."""

    text: str
    rationale: str | None = None
    risk_if_wrong: RiskLevel = RiskLevel.LOW


class ResearchScope(BaseModel):
    """The bounded scope of a research investigation."""

    model_config = ConfigDict(frozen=True)

    included_topics: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    required_dimensions: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    time_range: TimeRange | None = None
    source_constraints: SourceConstraints = Field(default_factory=SourceConstraints)
    definitions: list[Definition] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = Field(default_factory=utc_now)
