"""Source record types."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas._time import utc_now
from deep_research.schemas.scope import SourceType


class AuthorityClass(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class SourcePolicyStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_QUALIFICATION = "accepted_with_qualification"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AccessClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SourceRecord(BaseModel):
    """A retrieved and appraised source."""

    source_id: str
    canonical_uri: str
    title: str = ""
    publisher: str | None = None
    author: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    source_type: SourceType = SourceType.OTHER
    authority_class: AuthorityClass = AuthorityClass.UNKNOWN
    independence_cluster_id: str | None = None
    content_hash: str = ""
    snapshot_uri: str | None = None
    language: str = "en"
    jurisdiction: str | None = None
    access_classification: AccessClassification = AccessClassification.PUBLIC
    trust_score: float = 0.5
    freshness_score: float = 0.5
    policy_status: SourcePolicyStatus = SourcePolicyStatus.ACCEPTED
    rejection_reason: str | None = None
