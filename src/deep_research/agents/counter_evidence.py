"""Counter-Evidence Agent — searches for contradictions against claims.

LLM-backed agent that challenges high-materiality claims with counter-evidence search.
Falls back to stub logic when LLM is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import generate_structured, get_model_for_stage, is_llm_available

logger = logging.getLogger(__name__)


async def counter_evidence_agent(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Search for contradictions and counter-evidence against claims.

    Triggered for: material claims (high/critical), causal claims,
    vendor-comparative claims, and recommendations.

    Args:
        claims: List of claim dicts with {claim_id, text, claim_type, materiality, evidence_ids}.
        evidence: Current evidence records.
        sources: Current source records.

    Returns:
        Dict with {contradictions_found, counter_evidence, independence_issues, recommendations}.
    """
    ev = evidence or []
    srcs = sources or []

    # Filter claims that need counter-evidence
    target_claims = [
        c for c in claims
        if c.get("materiality") in ("high", "critical")
        or str(c.get("claim_type")).lower() in ("causal", "comparative", "recommendation")
    ]

    if not target_claims:
        return {
            "contradictions_found": [],
            "counter_evidence": [],
            "independence_issues": [],
            "recommendations": [],
            "summary": "No claims require counter-evidence search.",
        }

    # Try LLM path
    if is_llm_available():
        try:
            prompt = _build_counter_evidence_prompt(target_claims, ev)
            response = await generate_structured(
                prompt,
                model=get_model_for_stage("contradictions_search"),
                temperature=0.2,
                max_output_tokens=2048,
            )
            return _parse_counter_evidence_response(response, target_claims)
        except Exception as exc:
            logger.warning("Counter-evidence LLM call failed: %s — using stub", exc)

    # Stub fallback
    return _stub_counter_evidence(target_claims, ev, srcs)


def _build_counter_evidence_prompt(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> str:
    """Build prompt for counter-evidence analysis."""
    claim_lines = []
    for c in claims[:5]:  # Limit to avoid token overflow
        claim_lines.append(
            f"  - [{c.get('claim_id')}] type={c.get('claim_type')} "
            f"mat={c.get('materiality')}: {c.get('text', '')[:200]}"
        )

    ev_lines = []
    for e in evidence[:10]:
        ev_lines.append(f"  - {e.get('exact_excerpt', '')[:200]}")

    return f"""You are a skeptical counter-evidence analyst. For each claim below, identify:

1. Potential contradictions in the existing evidence
2. What counter-evidence should be searched for
3. Whether sources appear independent

Claims:
{chr(10).join(claim_lines)}

Existing Evidence:
{chr(10).join(ev_lines)}

Return analysis:
COUNTER: <claim_id> | <contradiction or "none"> | <recommended counter-search query>
INDEPENDENCE: <claim_id> | <independent/clustered> | <rationale>
"""


def _parse_counter_evidence_response(
    response: str,
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Parse LLM counter-evidence response."""
    contradictions_found = []
    independence_issues = []

    for line in response.strip().split("\n"):
        line = line.strip()
        if line.startswith("COUNTER:"):
            parts = [p.strip() for p in line[8:].split("|")]
            if len(parts) >= 2 and parts[1].lower() != "none":
                contradictions_found.append({
                    "claim_id": parts[0],
                    "contradiction": parts[1] if len(parts) > 1 else "",
                    "recommended_query": parts[2] if len(parts) > 2 else "",
                })
        elif line.startswith("INDEPENDENCE:"):
            parts = [p.strip() for p in line[13:].split("|")]
            if len(parts) >= 2 and "clustered" in parts[1].lower():
                independence_issues.append({
                    "claim_id": parts[0],
                    "status": parts[1] if len(parts) > 1 else "unknown",
                    "rationale": parts[2] if len(parts) > 2 else "",
                })

    return {
        "contradictions_found": contradictions_found,
        "counter_evidence": [],
        "independence_issues": independence_issues,
        "recommendations": [
            {"action": "search_contradictions", "claims": [c["claim_id"] for c in contradictions_found]}
        ] if contradictions_found else [],
        "summary": f"Found {len(contradictions_found)} potential contradictions, {len(independence_issues)} independence concerns.",
    }


def _stub_counter_evidence(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stub counter-evidence when LLM is unavailable."""
    # Check for vendor sources without independent corroboration
    independence_issues = []
    vendor_sources = [s for s in sources if str(s.get("source_type", "")).lower() == "vendor"]
    non_vendor = [s for s in sources if str(s.get("source_type", "")).lower() != "vendor"]

    if vendor_sources and not non_vendor:
        for c in claims:
            if c.get("claim_type") in ("comparative", "recommendation"):
                independence_issues.append({
                    "claim_id": c.get("claim_id", ""),
                    "status": "vendor_only",
                    "rationale": "All sources are vendor-authored — independence not established",
                })

    return {
        "contradictions_found": [],
        "counter_evidence": [],
        "independence_issues": independence_issues,
        "recommendations": [
            {"action": "search_independent_sources", "note": "Need non-vendor sources"}
        ] if independence_issues else [],
        "summary": f"Stub: {len(independence_issues)} independence concerns detected (LLM unavailable).",
    }
