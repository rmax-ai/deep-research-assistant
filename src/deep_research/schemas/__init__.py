"""Deep Research Assistant — Core schema models.

All Pydantic models for the research state machine.
"""

from deep_research.schemas.approval import ApprovalDecision, ApprovalGate
from deep_research.schemas.claim import (
    Claim,
    ClaimType,
    EpistemicStatus,
    InferenceOperation,
    InferenceStep,
    Materiality,
    ReviewStatus,
)
from deep_research.schemas.contradiction import (
    Contradiction,
    ContradictionType,
    ResolutionStatus,
)
from deep_research.schemas.draft import MissingClaim, SectionDraft
from deep_research.schemas.evidence import EvidenceFragment, EvidenceType
from deep_research.schemas.metrics import ResearchMetrics, StoppingDecision
from deep_research.schemas.outline import Outline, OutlineSection, SectionStatus
from deep_research.schemas.perspective import Perspective, PerspectiveStatus
from deep_research.schemas.question import (
    QuestionEdge,
    QuestionGraph,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    ResearchQuestion,
)
from deep_research.schemas.run import (
    DepthLevel,
    OutputType,
    ResearchBudget,
    ResearchMode,
    ResearchObjective,
    ResearchRun,
    RunStatus,
)
from deep_research.schemas.scope import (
    Assumption,
    Definition,
    ResearchScope,
    RiskLevel,
    SourceConstraints,
    SourceMix,
    SourceType,
    TimeRange,
)
from deep_research.schemas.search import (
    FreshnessRequirement,
    SearchPlan,
    SearchQuery,
    StopCondition,
)
from deep_research.schemas.source import (
    AccessClassification,
    AuthorityClass,
    SourcePolicyStatus,
    SourceRecord,
)
from deep_research.schemas.verification import (
    VerificationFinding,
    VerificationReport,
    VerificationSeverity,
)

# Rebuild models with forward references to resolve string annotations.
# Must happen after all schema modules are imported.

ResearchRun.model_rebuild()

__all__ = [
    "AccessClassification",
    # Approval
    "ApprovalDecision",
    "ApprovalGate",
    "Assumption",
    "AuthorityClass",
    # Claim
    "Claim",
    "ClaimType",
    # Contradiction
    "Contradiction",
    "ContradictionType",
    "Definition",
    "DepthLevel",
    "EpistemicStatus",
    # Evidence
    "EvidenceFragment",
    "EvidenceType",
    "FreshnessRequirement",
    "InferenceOperation",
    "InferenceStep",
    "Materiality",
    "MissingClaim",
    # Outline
    "Outline",
    "OutlineSection",
    "OutputType",
    # Perspective
    "Perspective",
    "PerspectiveStatus",
    "QuestionEdge",
    "QuestionGraph",
    "QuestionOrigin",
    "QuestionStatus",
    "QuestionType",
    "ResearchBudget",
    # Metrics
    "ResearchMetrics",
    "ResearchMode",
    "ResearchObjective",
    # Question
    "ResearchQuestion",
    # Run
    "ResearchRun",
    # Scope
    "ResearchScope",
    "ResolutionStatus",
    "ReviewStatus",
    "RiskLevel",
    "RunStatus",
    # Search
    "SearchPlan",
    "SearchQuery",
    # Draft
    "SectionDraft",
    "SectionStatus",
    "SourceConstraints",
    "SourceMix",
    "SourcePolicyStatus",
    # Source
    "SourceRecord",
    "SourceType",
    "StopCondition",
    "StoppingDecision",
    "TimeRange",
    # Verification
    "VerificationFinding",
    "VerificationReport",
    "VerificationSeverity",
]
