"""Verification Agent — independent review of draft reports.

LLM-backed agent using distinct prompts from the section writer.
Checks for unsupported synthesis, missing qualifications, causal overreach,
and cross-section consistency.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import generate_structured, get_model_for_tier, is_llm_available
from deep_research.nodes.verification import verify_draft_citations

logger = logging.getLogger(__name__)


async def verifier(
    drafts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify draft reports against approved claims and evidence.

    Uses distinct model/prompt from section writer (independence rule).

    Args:
        drafts: List of section draft dicts with {content, cited_claim_ids}.
        claims: Approved claim records.
        evidence: Evidence fragment records.

    Returns:
        Dict with {findings, passed, blocking_findings, major_findings}.
    """
    if not drafts:
        return {
            "findings": [],
            "passed": True,
            "blocking_findings": 0,
            "major_findings": 0,
        }

    # Always run heuristic entailment check (no LLM required)
    citation_check = verify_draft_citations(drafts, claims, evidence)
    findings = list(citation_check.get("findings", []))

    # Try LLM path for semantic verification (cross-section, causal overreach)
    if is_llm_available():
        try:
            prompt = _build_verifier_prompt(drafts, claims)
            response = await generate_structured(
                prompt,
                model=get_model_for_tier("verification"),
                temperature=0.1,  # Lower temperature than writer for precision
                system_instruction=(
                    "You are a fact-checker and verification agent. "
                    "Your job is to find unsupported claims, missing qualifications, "
                    "and causal overreach. Be precise and specific. "
                    "Flag only real issues — do not invent problems."
                ),
                max_output_tokens=2048,
            )
            semantic_findings = _parse_verifier_response(response)
            findings.extend(semantic_findings)
        except Exception as exc:
            logger.warning("Verifier LLM call failed: %s", exc)
    else:
        logger.info("LLM unavailable — using heuristic verification only")
        # Add cross-section consistency check (deterministic)
        cross_section_findings = _cross_section_consistency(drafts, claims)
        findings.extend(cross_section_findings)

    blocking = sum(1 for f in findings if f.get("severity") == "blocking")
    major = sum(1 for f in findings if f.get("severity") == "major")

    return {
        "findings": findings,
        "blocking_findings": blocking,
        "major_findings": major,
        "minor_findings": sum(1 for f in findings if f.get("severity") == "minor"),
        "passed": blocking == 0,
    }


def _build_verifier_prompt(
    drafts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> str:
    """Build verification prompt — distinct from writer prompt."""
    draft_text = "\n\n".join(
        d.get("content", "")[:500] for d in drafts[:3]
    )
    claim_text = "\n".join(
        f"  - [{c.get('claim_id')}] ({c.get('epistemic_status')}) {c.get('text', '')[:200]}"
        for c in claims[:20]
    )

    return f"""Verify the following draft report sections against the approved claims registry.

## Approved Claims (source of truth)
{claim_text}

## Draft Sections (to verify)
{draft_text}

For each draft section, identify:

1. UNSUPPORTED: Statements not backed by any approved claim
2. OVERREACH: Claims presented as stronger than their epistemic status allows
3. MISSING_QUALIFIER: Important qualifications dropped from the claim
4. CROSS_SECTION: Contradictions between sections

Return one finding per line:
FINDING: <type> | <severity: blocking/major/minor> | <section> | <description>
"""


def _parse_verifier_response(response: str) -> list[dict[str, Any]]:
    """Parse verifier LLM response into findings."""
    findings: list[dict[str, Any]] = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line.startswith("FINDING:"):
            parts = [p.strip() for p in line[8:].split("|", 3)]
            if len(parts) >= 3:
                findings.append({
                    "finding_id": f"vrf-{len(findings):03d}",
                    "type": parts[0],
                    "severity": parts[1] if parts[1] in ("blocking", "major", "minor") else "major",
                    "section": parts[2] if len(parts) > 2 else "",
                    "message": parts[3] if len(parts) > 3 else "",
                })
    return findings


def _cross_section_consistency(
    drafts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministic cross-section consistency check.

    Checks for contradictory claim references across sections.
    """
    findings: list[dict[str, Any]] = []
    claim_refs: dict[str, set[str]] = {}  # claim_id → {section_titles}

    for draft in drafts:
        section = draft.get("section_title", draft.get("title", "unknown"))
        for cid in draft.get("cited_claim_ids", []):
            claim_refs.setdefault(cid, set()).add(section)

    # Check for claims cited in multiple sections with different framing
    # (potential inconsistency)
    for cid, sections in claim_refs.items():
        if len(sections) > 1:
            claim = next((c for c in claims if c.get("claim_id") == cid), None)
            if claim and claim.get("epistemic_status") in ("disputed", "speculative"):
                findings.append({
                    "finding_id": f"cs-{len(findings):03d}",
                    "type": "cross_section_duplicate",
                    "severity": "minor",
                    "message": f"Disputed/speculative claim {cid} cited in {len(sections)} sections: {sections}",
                })

    return findings
