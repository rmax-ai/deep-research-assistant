"""Claim confidence scoring model for epistemic reliability.

Deterministic node — computes confidence from source authority, independence,
relevance, freshness, corroboration, qualifications, claim type, and verification.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

# ── Confidence labels ─────────────────────────────────────────────────────


def confidence_label(score: float) -> str:
    """Map numeric confidence to user-facing label."""
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"


# ── Claim-relative source authority ───────────────────────────────────────

_AUTHORITY_BASE: dict[str, float] = {
    "primary": 0.9,
    "standard": 0.85,
    "academic": 0.8,
    "official": 0.8,
    "expert_analysis": 0.65,
    "technical_report": 0.6,
    "vendor": 0.45,
    "news": 0.4,
    "blog": 0.25,
    "forum": 0.15,
    "unknown": 0.2,
}

_VENDOR_CLAIM_PENALTY = 0.35  # Penalty for vendor claims about market/superiority


def _source_authority(source: dict[str, Any]) -> float:
    """Compute base source authority from source type."""
    src_type = str(source.get("source_type", "unknown")).lower()
    return _AUTHORITY_BASE.get(src_type, 0.2)


def _claim_relative_authority(
    claim: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> float:
    """Claim-relative source authority.

    A vendor may be high-authority for API docs, low-authority for market claims.
    """
    evidence_ids = claim.get("evidence_ids", [])
    if not evidence_ids:
        return 0.3

    authorities = []
    for eid in evidence_ids:
        src = sources.get(eid, sources.get(str(eid), {}))
        auth = _source_authority(src)

        # Vendor claim penalty for comparative/superiority claims
        claim_type = str(claim.get("claim_type", "")).lower()
        src_type = str(src.get("source_type", "")).lower()
        if src_type == "vendor" and claim_type in ("comparative", "normative", "recommendation"):
            auth = max(0.1, auth - _VENDOR_CLAIM_PENALTY)

        authorities.append(auth)

    return sum(authorities) / len(authorities) if authorities else 0.3


# ── Independence ──────────────────────────────────────────────────────────

def _source_independence(
    claim: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> float:
    """Score source independence — multiple independent sources = higher score."""
    evidence_ids = claim.get("evidence_ids", [])
    if len(evidence_ids) < 2:
        return 0.5 if len(evidence_ids) == 1 else 0.3

    clusters: set[str] = set()
    for eid in evidence_ids:
        src = sources.get(eid, sources.get(str(eid), {}))
        cluster = str(src.get("independence_cluster_id", eid))
        clusters.add(cluster)

    # More independent clusters = higher score
    ratio = len(clusters) / len(evidence_ids)
    return min(1.0, 0.4 + 0.6 * ratio)


# ── Freshness ─────────────────────────────────────────────────────────────

def _evidence_freshness(
    claim: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> float:
    """Score evidence freshness — newer sources score higher."""
    evidence_ids = claim.get("evidence_ids", [])
    now = datetime.now(UTC).date()
    freshness_scores = []

    for eid in evidence_ids:
        src = sources.get(eid, sources.get(str(eid), {}))
        pub_str = src.get("publication_date", "")
        if pub_str:
            try:
                pub = date.fromisoformat(str(pub_str))
                age_days = (now - pub).days
                if age_days <= 90:
                    freshness_scores.append(1.0)
                elif age_days <= 365:
                    freshness_scores.append(0.8)
                elif age_days <= 730:
                    freshness_scores.append(0.5)
                elif age_days <= 1825:  # 5 years
                    freshness_scores.append(0.3)
                else:
                    freshness_scores.append(0.15)
            except (ValueError, TypeError):
                freshness_scores.append(0.5)
        else:
            freshness_scores.append(0.4)

    return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.3


# ── Main confidence function ──────────────────────────────────────────────

def compute_claim_confidence(
    claim: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    verification_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute confidence for a single claim.

    Confidence(c) = f(authority, independence, relevance, freshness,
                       corroboration, qualifications, claim_type, verification)

    Args:
        claim: Claim dict with at least {claim_id, text, claim_type, evidence_ids, epistemic_status}.
        sources: Dict of source_id → source dict.
        verification_result: Optional verification findings for this claim.

    Returns:
        Dict with {confidence, label, rationale_factors}.
    """
    auth = _claim_relative_authority(claim, sources)
    indep = _source_independence(claim, sources)
    fresh = _evidence_freshness(claim, sources)

    # Corroboration: more evidence = higher confidence (with diminishing returns)
    evidence_count = len(claim.get("evidence_ids", []))
    corr = min(1.0, 0.3 + 0.35 * min(evidence_count, 3))

    # Claim type base confidence
    claim_type = str(claim.get("claim_type", "descriptive")).lower()
    type_base: dict[str, float] = {
        "definitional": 0.7,
        "descriptive": 0.6,
        "mechanistic": 0.55,
        "comparative": 0.45,
        "historical": 0.55,
        "causal": 0.35,
        "normative": 0.4,
        "quantitative": 0.55,
        "implementation": 0.5,
        "security": 0.4,
        "failure_mode": 0.4,
        "counterfactual": 0.3,
        "evidence_challenge": 0.5,
        "recommendation": 0.35,
    }
    claim_type_score = type_base.get(claim_type, 0.5)

    # Epistemic status modifier
    epistemic = str(claim.get("epistemic_status", "inferred")).lower()
    epistemic_mod: dict[str, float] = {
        "source-stated": 0.85,
        "directly observed": 0.9,
        "extracted": 0.7,
        "corroborated": 0.8,
        "inferred": 0.55,
        "causal-inference": 0.4,
        "disputed": 0.2,
        "speculative": 0.25,
        "recommendation": 0.4,
        "unresolved": 0.15,
    }

    # Verification modifier
    verif_score = 1.0
    if verification_result:
        findings = verification_result.get("findings", [])
        if findings:
            blocking = sum(1 for f in findings if f.get("severity") == "blocking")
            major = sum(1 for f in findings if f.get("severity") == "major")
            verif_score = max(0.1, 1.0 - (0.3 * blocking) - (0.1 * major))

    confidence = (
        0.25 * auth
        + 0.15 * indep
        + 0.10 * fresh
        + 0.15 * corr
        + 0.15 * claim_type_score
        + 0.10 * epistemic_mod.get(epistemic, 0.5)
        + 0.10 * verif_score
    )

    confidence = round(max(0.0, min(1.0, confidence)), 3)

    return {
        "claim_id": claim.get("claim_id", ""),
        "confidence": confidence,
        "label": confidence_label(confidence),
        "factors": {
            "authority": round(auth, 3),
            "independence": round(indep, 3),
            "freshness": round(fresh, 3),
            "corroboration": round(corr, 3),
            "claim_type_score": round(claim_type_score, 3),
            "epistemic_modifier": round(epistemic_mod.get(epistemic, 0.5), 3),
            "verification_modifier": round(verif_score, 3),
        },
    }


def score_all_claims(
    claims: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    verification_results: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compute confidence for all claims."""
    results = []
    vrf = verification_results or {}
    for claim in claims:
        cid = claim.get("claim_id", "")
        results.append(compute_claim_confidence(
            claim, sources, vrf.get(cid),
        ))
    return results
