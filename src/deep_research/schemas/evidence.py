"""Evidence fragment types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from deep_research.schemas.scope import TimeRange


class EvidenceType(StrEnum):
    DIRECT_QUOTE = "direct_quote"
    DATA_POINT = "data_point"
    API_SPECIFICATION = "api_specification"
    ARCHITECTURE_DESCRIPTION = "architecture_description"
    PERFORMANCE_METRIC = "performance_metric"
    SECURITY_ASSERTION = "security_assertion"
    REGULATORY_REQUIREMENT = "regulatory_requirement"
    INCIDENT_RECORD = "incident_record"
    EXPERT_OPINION = "expert_opinion"
    VENDOR_CLAIM = "vendor_claim"
    OTHER = "other"


class EvidenceFragment(BaseModel):
    """An extracted piece of evidence from a source."""

    evidence_id: str
    source_id: str
    locator: str = ""  # e.g., paragraph number, section heading, line range
    exact_excerpt: str
    normalized_statement: str = ""
    surrounding_context: str = ""
    extraction_method: str = "llm"  # llm, regex, manual
    extraction_model: str | None = None
    evidence_type: EvidenceType = EvidenceType.OTHER
    temporal_scope: TimeRange | None = None
    qualifiers: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    content_hash: str = ""
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
