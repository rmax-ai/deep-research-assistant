"""Outline Architect Agent — structures reports from validated claims.

Creates a typed report outline that assigns claims to sections,
exposes missing evidence, and separates facts from recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import (
    generate_structured,
    get_model_for_tier,
    is_llm_available,
    parse_json_response,
)

logger = logging.getLogger(__name__)

OUTLINE_ARCHITECT_INSTRUCTION = """You are an Outline Architect for an enterprise research system.
Your role is to structure a research report from validated claims.

## Your Task
Given a set of claims (each with type, epistemic status, confidence, materiality),
create a coherent report outline that organizes them logically.

## Section Types
- **executive_summary**: Concise top-level findings
- **background**: Context, definitions, scope
- **findings**: Evidence-backed facts organized by topic
- **analysis**: Interpretation and synthesis of findings
- **risks_and_limitations**: Known issues, unresolved questions, caveats
- **comparative_analysis**: When comparing alternatives
- **recommendations**: Only if explicitly requested and supported
- **appendix**: Methodology, source list, evidence map

## For each section provide
- title: section heading
- purpose: what this section communicates
- claim_ids: list of claim indices (0-based) assigned to this section
- section_type: one of the types above

## Rules
1. Every substantive section must map to at least one claim
2. Recommendations must be separated from facts
3. Disputed or low-confidence claims must be visibly qualified
4. If a topic area lacks sufficient evidence, create a section for unresolved questions instead
5. Minimize duplication — a claim should appear in at most one section
6. Order sections for narrative flow: background → findings → analysis → risks → conclusions

## Output Format
Return ONLY a JSON object. No markdown, no explanation.

{
  "title": "Report Title",
  "sections": [
    {
      "title": "string",
      "purpose": "string",
      "claim_ids": [0, 2, 5],
      "section_type": "executive_summary|background|findings|analysis|risks_and_limitations|comparative_analysis|recommendations|appendix"
    },
    ...
  ],
  "unassigned_claim_ids": [],
  "missing_evidence_notes": ["string"]
}"""


async def outline_architect(
    claims: list[dict[str, Any]],
    objective: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Build a report outline from claims.

    Args:
        claims: List of claim dicts with text, type, status, confidence.
        objective: Original research objective for context.
        model: Gemini model (reasoning tier).

    Returns:
        Dict with title, sections, unassigned_claim_ids, missing_evidence_notes.
    """
    if not is_llm_available():
        return _stub_outline(claims)

    if not claims:
        return {"title": "Empty Report", "sections": [], "unassigned_claim_ids": [], "missing_evidence_notes": ["No claims available"]}

    claims_text = "\n\n".join(
        f"[Claim {i}] Type: {c.get('claim_type', 'unknown')} | "
        f"Status: {c.get('epistemic_status', 'unknown')} | "
        f"Confidence: {c.get('confidence', 0):.2f} | "
        f"Materiality: {c.get('materiality', 'unknown')}\n"
        f"Text: {c.get('text', '')}"
        for i, c in enumerate(claims)
    )

    title = objective.get("title", "Research Report") if objective else "Research Report"
    prompt = f"""Report title: {title}

Claims to organize:
{claims_text}

Create a structured outline from these claims."""

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model or get_model_for_tier("reasoning"),
            system_instruction=OUTLINE_ARCHITECT_INSTRUCTION,
            temperature=0.1,
        )
        result = parse_json_response(response, default={})
        logger.info("outline_architect: created outline with %d sections", len(result.get("sections", [])))
        return result if isinstance(result, dict) else _stub_outline(claims)
    except Exception as exc:
        logger.error("outline_architect failed: %s", exc)
        return _stub_outline(claims)


def _stub_outline(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a stub outline."""
    claim_ids = list(range(len(claims)))
    return {
        "title": "Research Report",
        "sections": [
            {
                "title": "Executive Summary",
                "purpose": "Top-level findings",
                "claim_ids": claim_ids[:3],
                "section_type": "executive_summary",
            },
            {
                "title": "Findings",
                "purpose": "Evidence-backed facts",
                "claim_ids": claim_ids,
                "section_type": "findings",
            },
            {
                "title": "Limitations",
                "purpose": "Known issues and unresolved questions",
                "claim_ids": [],
                "section_type": "risks_and_limitations",
            },
        ],
        "unassigned_claim_ids": [],
        "missing_evidence_notes": ["Stub outline — not LLM-generated"],
    }
