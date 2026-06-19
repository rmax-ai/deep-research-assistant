"""Contradiction detection and resolution tracking for epistemic reliability.

Deterministic node — detects conflicting claims from evidence and tracks resolution state.
"""

from __future__ import annotations

import enum
from typing import Any


class ContradictionType(enum.Enum):
    DIRECT_FACTUAL = "direct_factual"
    TEMPORAL = "temporal"
    DEFINITIONAL = "definitional"
    SCOPE_MISMATCH = "scope_mismatch"
    METHODOLOGICAL = "methodological"
    CAUSAL = "causal"
    INTERPRETATION = "interpretation"
    SOURCE_SUPERSESSION = "source_supersession"


class ResolutionStatus(enum.Enum):
    UNRESOLVED = "unresolved"
    RESOLVED_FAVORING_A = "resolved_favoring_a"
    RESOLVED_FAVORING_B = "resolved_favoring_b"
    EXPLAINED = "explained"
    DEFERRED = "deferred"


def _normalize(text: str) -> str:
    """Simple normalization for comparison: lowercase, strip punctuation."""
    return " ".join(text.lower().split())


def _claims_conflict(c1: dict[str, Any], c2: dict[str, Any]) -> str | None:
    """Check if two claims conflict. Returns contradiction type or None."""
    t1 = _normalize(c1.get("text", ""))
    t2 = _normalize(c2.get("text", ""))

    # Trivially identical claims don't conflict
    if t1 == t2:
        return None

    # Check for negation patterns
    negators = {"not", "no", "never", "cannot", "unable", "impossible", "failed"}
    words1 = set(t1.split())
    words2 = set(t2.split())

    if words1 & negators and not (words2 & negators):
        return ContradictionType.DIRECT_FACTUAL.value
    if words2 & negators and not (words1 & negators):
        return ContradictionType.DIRECT_FACTUAL.value

    # Check temporal scope mismatch (dates in one but not the other)
    has_date_1 = any(c.isdigit() for c in t1)
    has_date_2 = any(c.isdigit() for c in t2)
    if has_date_1 != has_date_2:
        return ContradictionType.TEMPORAL.value

    # Check source supersession (one source newer)
    src1 = c1.get("source_published", "")
    src2 = c2.get("source_published", "")
    if src1 and src2 and src1 != src2:
        return ContradictionType.SOURCE_SUPERSESSION.value

    return None


def detect_contradictions(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Detect contradictions between claims.

    Compares all claim pairs for conflicts and returns structured contradiction records.

    Args:
        claims: List of claim dicts with at least {claim_id, text}.
        evidence: Optional evidence records for context.

    Returns:
        List of contradiction dicts: {contradiction_id, claim_ids, type, explanation, resolution_status, materiality}.
    """
    contradictions: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for i, c1 in enumerate(claims):
        for j, c2 in enumerate(claims):
            if i >= j:
                continue
            pid1 = c1.get("claim_id", str(i))
            pid2 = c2.get("claim_id", str(j))
            if (pid1, pid2) in seen_pairs or (pid2, pid1) in seen_pairs:
                continue
            seen_pairs.add((pid1, pid2))

            conflict_type = _claims_conflict(c1, c2)
            if conflict_type:
                contradictions.append({
                    "contradiction_id": f"contra-{len(contradictions):03d}",
                    "claim_ids": [pid1, pid2],
                    "type": conflict_type,
                    "explanation": f"Claim '{c1.get('text','')[:80]}' conflicts with '{c2.get('text','')[:80]}'",
                    "possible_resolution": None,
                    "resolution_status": ResolutionStatus.UNRESOLVED.value,
                    "materiality": max(
                        c1.get("materiality", "medium"),
                        c2.get("materiality", "medium"),
                        key=lambda m: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(m, 1),
                    ),
                })

    return contradictions


def track_resolution(
    contradictions: list[dict[str, Any]],
    resolution_updates: dict[str, str],
) -> list[dict[str, Any]]:
    """Apply resolution status updates to contradictions.

    Args:
        contradictions: Existing contradiction records.
        resolution_updates: Mapping of contradiction_id → resolution_status.

    Returns:
        Updated contradiction list.
    """
    for c in contradictions:
        cid = c.get("contradiction_id", "")
        if cid in resolution_updates:
            c["resolution_status"] = resolution_updates[cid]
    return contradictions


def get_unresolved_material(
    contradictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return unresolved contradictions on material/high claims."""
    return [
        c for c in contradictions
        if c.get("resolution_status") == ResolutionStatus.UNRESOLVED.value
        and c.get("materiality") in ("high", "critical")
    ]
