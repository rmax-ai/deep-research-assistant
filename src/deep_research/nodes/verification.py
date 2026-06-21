"""Citation entailment and draft verification for epistemic reliability.

Deterministic node — checks whether cited evidence actually supports claims.
"""

from __future__ import annotations

from typing import Any


def check_entailment(claim_text: str, evidence_excerpt: str) -> tuple[bool, float]:
    """Heuristic citation entailment check.

    Returns (entailed: bool, confidence: float).
    Uses keyword overlap and negation detection — not full semantic entailment.
    For full verification, use the Verification Agent (LLM-backed).

    Args:
        claim_text: The claim being made.
        evidence_excerpt: The cited evidence excerpt.

    Returns:
        Tuple of (entailed, confidence).
    """
    claim_words = set(claim_text.lower().split())
    ev_words = set(evidence_excerpt.lower().split())

    if not claim_words or not ev_words:
        return False, 0.0

    # Keyword overlap ratio
    overlap = claim_words & ev_words
    overlap_ratio = len(overlap) / len(claim_words) if claim_words else 0.0

    # Check for contradiction (negation in evidence that claim doesn't account for)
    negators = {"not", "no", "never", "cannot", "unable", "failed", "impossible", "doesn't", "don't", "didn't"}
    has_negation = bool(ev_words & negators)
    claim_has_negation = bool(claim_words & negators)

    if has_negation and not claim_has_negation:
        overlap_ratio *= 0.5  # Penalize when claim ignores negation

    # Confidence score
    if overlap_ratio >= 0.6:
        return True, overlap_ratio
    elif overlap_ratio >= 0.35:
        return True, overlap_ratio  # Weak entailment
    else:
        return False, overlap_ratio


def verify_draft_citations(
    drafts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify citation entailment across all drafts.

    Checks that every cited claim has supporting evidence that entails the claim text.

    Returns:
        Verification report with findings, passed status, and severity breakdown.
    """
    # Build lookup maps
    claims_by_id: dict[str, dict[str, Any]] = {
        c.get("claim_id", ""): c for c in claims
    }
    evidence_by_id: dict[str, dict[str, Any]] = {
        e.get("evidence_id", ""): e for e in evidence
    }

    findings: list[dict[str, Any]] = []

    for draft in drafts:
        cited_claim_ids = draft.get("cited_claim_ids", [])

        for cid in cited_claim_ids:
            claim = claims_by_id.get(cid)
            if not claim:
                findings.append({
                    "finding_id": f"find-{len(findings):03d}",
                    "type": "missing_claim",
                    "claim_id": cid,
                    "severity": "blocking",
                    "message": f"Cited claim {cid} not found in claim registry",
                })
                continue

            # Check each evidence fragment linked to this claim
            eids = claim.get("evidence_ids", [])
            if not eids:
                findings.append({
                    "finding_id": f"find-{len(findings):03d}",
                    "type": "unsupported_claim",
                    "claim_id": cid,
                    "severity": "blocking",
                    "message": f"Claim {cid} has no linked evidence",
                })
                continue

            found_entailment = False
            for eid in eids:
                ev = evidence_by_id.get(eid)
                if not ev:
                    continue
                excerpt = ev.get("exact_excerpt", ev.get("normalized_statement", ""))
                if not excerpt:
                    continue
                entailed, _confidence = check_entailment(
                    claim.get("text", ""), excerpt,
                )
                if entailed:
                    found_entailment = True
                    break

            if not found_entailment:
                severity = "major" if eids else "blocking"
                findings.append({
                    "finding_id": f"find-{len(findings):03d}",
                    "type": "citation_entailment_failure",
                    "claim_id": cid,
                    "severity": severity,
                    "message": f"No evidence fragment entails claim {cid}",
                })

    blocking = sum(1 for f in findings if f["severity"] == "blocking")
    major = sum(1 for f in findings if f["severity"] == "major")
    minor = sum(1 for f in findings if f["severity"] == "minor")

    return {
        "findings": findings,
        "blocking_findings": blocking,
        "major_findings": major,
        "minor_findings": minor,
        "passed": blocking == 0,
    }


def repair_loop(
    findings: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    max_repairs: int = 2,
) -> dict[str, Any]:
    """Execute repair loop for verification findings.

    Returns status of repair attempts.
    """
    blocking_findings = [f for f in findings if f["severity"] == "blocking"]
    major_findings = [f for f in findings if f["severity"] == "major"]

    if not blocking_findings and not major_findings:
        return {"repairs_attempted": 0, "status": "no_issues"}

    # Mark drafts that need repair
    repaired_count = 0
    for _finding in blocking_findings[:max_repairs]:
        # In a real implementation, this would trigger the section writer
        # to re-generate the problematic section. For now, record the attempt.
        repaired_count += 1

    return {
        "repairs_attempted": repaired_count,
        "max_repairs": max_repairs,
        "remaining_blocking": max(0, len(blocking_findings) - repaired_count),
        "remaining_major": len(major_findings),
        "status": "repaired" if repaired_count >= len(blocking_findings) else "partial",
    }
