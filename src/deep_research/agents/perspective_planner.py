"""Perspective Planner Agent — discovers research lenses.

Generates non-overlapping research perspectives from scope,
always including mandatory defaults (foundational, architecture,
skeptical, enterprise).
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import generate_structured, is_llm_available, parse_json_response

logger = logging.getLogger(__name__)

PERSPECTIVE_PLANNER_INSTRUCTION = """You are a Perspective Planner for an enterprise research system.
Your role is to discover research lenses (perspectives) that cover a topic comprehensively.

## Your Task
Given a research scope, generate 4-6 research perspectives that provide comprehensive coverage.

## Mandatory Perspectives (always include)
1. **Foundational**: Basic facts, definitions, context, terminology
2. **Architecture/Implementation**: How things actually work, design, code, infrastructure
3. **Limitations & Failure Modes**: What can go wrong, edge cases, known issues, security
4. **Skeptical Counter-Analysis**: Challenge assumptions, find contrary evidence, test claims

## Optional (include when applicable)
5. **Enterprise Implications**: Operations, governance, compliance, cost, scaling
6. **Historical/Evolution**: How it developed, why choices were made, migration paths
7. **Standards/Regulatory**: Relevant standards, compliance requirements, legal context
8. **Comparative**: How it compares to alternatives

## For each perspective provide
- name: short identifier
- purpose: what this lens investigates
- required_questions: 2-3 specific questions this perspective must answer
- preferred_source_types: source types most relevant (official_documentation, standard, academic_paper, repository, vendor_whitepaper, incident_report, etc.)
- required_checks: specific validation steps (e.g., "STRIDE analysis", "verify against NIST SP 800-53")
- prohibited_actions: things this perspective must not do
- budget_weight: relative budget allocation (1.0 = equal share, sum should be ~4.0-6.0)

## Rules
1. Perspectives must not overlap semantically — if two perspectives would investigate the same thing, merge them.
2. For technical topics, spend more budget on architecture/implementation.
3. For security topics, spend more on limitations/failure modes and skeptical analysis.
4. Every perspective must have at least 2 required_questions.
5. Skip optional perspectives if the topic doesn't need them.

## Output Format
Return ONLY a JSON array of perspective objects. No markdown, no explanation.

[
  {
    "name": "string",
    "purpose": "string",
    "required_questions": ["string", ...],
    "preferred_source_types": ["string", ...],
    "required_checks": ["string", ...],
    "prohibited_actions": ["string", ...],
    "budget_weight": 1.0
  },
  ...
]"""


async def perspective_planner(
    scope: dict[str, Any],
    user_objective: str = "",
    model: str = "gemini-2.5-pro",
) -> list[dict[str, Any]]:
    """Generate research perspectives from scope.

    Args:
        scope: Research scope dict from Research Director.
        user_objective: Original user request for context.
        model: Gemini model to use.

    Returns:
        List of perspective dicts.
    """
    if not is_llm_available():
        logger.warning("LLM unavailable — returning stub perspectives")
        return _stub_perspectives()

    prompt = f"""Research scope:
{scope}

Original objective:
{user_objective}

Generate research perspectives for this topic."""

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model,
            system_instruction=PERSPECTIVE_PLANNER_INSTRUCTION,
            temperature=0.1,
        )
        result = parse_json_response(response, default=[])
        if isinstance(result, list):
            logger.info("perspective_planner: generated %d perspectives", len(result))
            return result
        return _stub_perspectives()
    except Exception as exc:
        logger.error("perspective_planner failed: %s", exc)
        return _stub_perspectives()


def _stub_perspectives() -> list[dict[str, Any]]:
    """Return mandatory default perspectives as stub."""
    return [
        {
            "name": "foundational",
            "purpose": "Basic facts, definitions, and context",
            "required_questions": ["What are the core concepts and terminology?"],
            "preferred_source_types": ["official_documentation", "standard"],
            "required_checks": [],
            "prohibited_actions": [],
            "budget_weight": 1.0,
        },
        {
            "name": "architecture",
            "purpose": "Implementation and design details",
            "required_questions": ["How is the system architected?"],
            "preferred_source_types": ["official_documentation", "repository"],
            "required_checks": [],
            "prohibited_actions": [],
            "budget_weight": 1.5,
        },
        {
            "name": "limitations",
            "purpose": "What can go wrong, known issues, failure modes",
            "required_questions": ["What are the known limitations and failure modes?"],
            "preferred_source_types": ["incident_report", "issue_tracker", "repository"],
            "required_checks": ["STRIDE analysis"],
            "prohibited_actions": [],
            "budget_weight": 1.5,
        },
        {
            "name": "skeptical",
            "purpose": "Challenge assumptions and claims with counter-evidence",
            "required_questions": ["What evidence contradicts common claims?", "Are sources independent?"],
            "preferred_source_types": ["academic_paper", "incident_report"],
            "required_checks": ["source independence check"],
            "prohibited_actions": [],
            "budget_weight": 1.0,
        },
        {
            "name": "enterprise",
            "purpose": "Operational, security, governance, and cost implications",
            "required_questions": ["What are the enterprise deployment considerations?"],
            "preferred_source_types": ["official_documentation", "vendor_whitepaper"],
            "required_checks": [],
            "prohibited_actions": [],
            "budget_weight": 1.0,
        },
    ]
