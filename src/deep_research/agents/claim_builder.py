"""Claim Builder Agent — converts evidence into atomic, traceable claims.

Atomizes compound statements, classifies epistemic status,
links to supporting evidence, and creates inference records.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import (
    generate_structured,
    get_model_for_stage,
    is_llm_available,
    parse_json_response,
)

logger = logging.getLogger(__name__)

CLAIM_BUILDER_INSTRUCTION = """You are a Claim Builder for an enterprise research system.
Your role is to convert evidence fragments into atomic, traceable claims.

## Your Task
Given evidence fragments extracted from sources, construct atomic claims.

## Atomicity Rule
A claim should normally contain **one subject, one predicate, and one principal qualification.**

❌ BAD: "ADK is secure, scalable, and better than competing frameworks."
✅ GOOD:
  - "ADK supports deployment to multiple runtime targets." (source-stated)
  - "ADK exposes authentication-related tool primitives." (source-stated)
  - "The available evidence does not establish superiority over competing frameworks." (speculative)

## Epistemic Status (assign exactly one per claim)
- **source_stated**: Directly present in a source text
- **extracted**: Derived from source content by the curator
- **corroborated**: Supported by multiple independent sources
- **inferred**: Synthesized across multiple sources
- **causal_inference**: Claims about causation (requires inference steps)
- **disputed**: Challenged by counter-evidence
- **speculative**: Insufficient support, flagged as uncertain
- **unresolved**: Pending further investigation

## For each claim provide
- text: the claim statement
- atomic_form: simplified subject-predicate-object form
- claim_type: factual, definitional, comparative, causal, predictive, recommendation, interpretation
- epistemic_status: one of the values above
- evidence_ids: list of evidence fragment indices (0-based) that support this claim
- supporting_claim_ids: indices of other claims this builds upon (empty if standalone)
- contradicting_claim_ids: indices of claims that contradict this one (empty if none)
- qualifiers: limitations or conditions on the claim
- confidence: 0.0-1.0
- materiality: low, medium, high, critical
- inference_steps: [] or list of {premise_claim_ids, operation (deduction/induction/abduction/analogy/causal_reasoning/synthesis/generalization), rationale} — required for inferred/causal_inference claims

## Output Format
Return ONLY a JSON object. No markdown, no explanation.

{
  "claims": [
    {
      "text": "string",
      "atomic_form": "string",
      "claim_type": "factual|definitional|comparative|causal|...",
      "epistemic_status": "source_stated|extracted|corroborated|...",
      "evidence_ids": [0, 1],
      "supporting_claim_ids": [],
      "contradicting_claim_ids": [],
      "qualifiers": ["string"],
      "confidence": 0.85,
      "materiality": "medium",
      "inference_steps": []
    },
    ...
  ]
}

## Rules
1. NEVER create a claim without linking it to at least one evidence fragment
2. Split compound claims aggressively — one idea per claim
3. Be conservative with confidence: one vendor source does not establish market superiority
4. Mark claims as speculative when evidence is thin
5. Include qualifiers that the original evidence itself mentions"""


async def claim_builder(
    evidence_fragments: list[dict[str, Any]],
    question: str = "",
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Build atomic claims from evidence fragments.

    Args:
        evidence_fragments: List of evidence fragment dicts.
        question: The research question being answered.
        model: Gemini model (reasoning tier).

    Returns:
        List of claim dicts.
    """
    if not is_llm_available():
        logger.warning("LLM unavailable — returning stub claims")
        return _stub_claims(evidence_fragments)

    if not evidence_fragments:
        return []

    evidence_text = "\n\n---\n\n".join(
        f"[Fragment {i}] Type: {f.get('evidence_type', 'unknown')}\n"
        f"Excerpt: {f.get('exact_excerpt', '')}\n"
        f"Normalized: {f.get('normalized_statement', '')}"
        for i, f in enumerate(evidence_fragments)
    )

    prompt = f"""Research question: {question}

Evidence fragments:
{evidence_text}

Build atomic claims from this evidence."""

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model or get_model_for_stage("claims_construct"),
            system_instruction=CLAIM_BUILDER_INSTRUCTION,
            temperature=0.1,
        )
        result = parse_json_response(response, default={"claims": []})
        claims = result.get("claims", []) if isinstance(result, dict) else []
        logger.info("claim_builder: built %d claims from %d fragments", len(claims), len(evidence_fragments))
        return claims if isinstance(claims, list) else _stub_claims(evidence_fragments)
    except Exception as exc:
        logger.error("claim_builder failed: %s", exc)
        return _stub_claims(evidence_fragments)


def _stub_claims(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return stub claims from evidence."""
    claims = []
    for i, f in enumerate(fragments):
        excerpt = f.get("exact_excerpt", "")[:200]
        if excerpt:
            claims.append({
                "text": excerpt,
                "atomic_form": excerpt[:100],
                "claim_type": "factual",
                "epistemic_status": "extracted",
                "evidence_ids": [i],
                "supporting_claim_ids": [],
                "contradicting_claim_ids": [],
                "qualifiers": ["stub claim — not LLM-verified"],
                "confidence": 0.3,
                "materiality": "medium",
                "inference_steps": [],
            })
    return claims
