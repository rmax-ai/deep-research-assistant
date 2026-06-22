"""Research Director Agent — scope interpretation and plan proposal.

Converts a natural-language research objective into a structured
ResearchPlanProposal with scope, perspectives, completion criteria,
budget, and approval recommendation.
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

RESEARCH_DIRECTOR_INSTRUCTION = """You are a Research Director for an enterprise-grade research assistant system.
Your role is to interpret research objectives and produce a structured research plan.

## Your Task
Given a user's research objective, produce a structured JSON research plan proposal.

## What to Include

### 1. Scope Classification
- Extract the core research topic and primary question
- Identify what IS in scope and what is explicitly OUT of scope
- Determine required dimensions (security, architecture, operations, cost, etc.)
- Identify relevant jurisdictions or time ranges if mentioned
- Assess risk level: low (informational), medium (technical decision), high (security/regulatory)
- List any explicit assumptions you must make due to ambiguity

### 2. Perspective Recommendations
Propose 4-6 research perspectives (lenses), always including:
- **Foundational**: Basic facts, definitions, and context
- **Architecture/Implementation**: How things actually work
- **Limitations & Failure Modes**: What can go wrong
- **Skeptical Counter-Analysis**: Challenge assumptions and claims
- **Enterprise Implications**: Operational, security, governance impact (if applicable)

### 3. Completion Criteria
Define concrete conditions that mark research as complete:
- What primary-source coverage is needed?
- What key questions must be answered?
- What contradictions must be explored?

### 4. Budget Recommendation
Estimate required resources:
- Number of searches expected
- Number of sources to open
- Depth level (overview / standard / deep / exhaustive)

### 5. Approval Recommendation
Recommend whether human approval is needed at key gates.
Be conservative: recommend approval for high-risk or ambiguous topics.

## Output Format
Return ONLY a JSON object. No markdown, no explanation outside the JSON.

{
  "objective": {
    "title": "string",
    "primary_question": "string",
    "decision_to_support": "string or null",
    "intended_audience": ["string", ...],
    "output_type": "technical_report|executive_brief|architecture_decision_record|evidence_map|comparison_matrix|risk_memo",
    "desired_depth": "overview|standard|deep|exhaustive",
    "language": "en"
  },
  "scope": {
    "included_topics": ["string", ...],
    "excluded_topics": ["string", ...],
    "required_dimensions": ["string", ...],
    "jurisdictions": ["string", ...],
    "time_range": {"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"} or null,
    "risk_level": "low|medium|high|critical",
    "definitions": [{"term": "string", "definition": "string"}, ...],
    "assumptions": [{"text": "string", "rationale": "string or null"}, ...]
  },
  "proposed_perspectives": [
    {
      "name": "string",
      "purpose": "string",
      "required_questions": ["string", ...],
      "preferred_source_types": ["official_documentation", "standard", "academic_paper", "repository", ...],
      "budget_weight": 1.0
    },
    ...
  ],
  "completion_criteria": [
    {"description": "string", "metric": "string", "threshold": "string"},
    ...
  ],
  "proposed_budget": {
    "searches": 80,
    "opened_sources": 50,
    "max_cost": 25.0,
    "max_wall_time_seconds": 1800
  },
  "approval_recommendation": {
    "scope_approval_required": true/false,
    "outline_approval_required": true/false,
    "publication_approval_required": true/false,
    "rationale": "string"
  }
}

## Rules
1. If the user's request is ambiguous, make reasonable assumptions and document them in scope.assumptions.
2. Do not ask clarifying questions — make your best judgment and flag uncertainty.
3. Be specific. "Security" is not a topic — "OWASP top 10 compliance for agent tool execution" is.
4. For technical topics, always include an implementation/architecture perspective.
5. For comparative topics, always include a skeptical counter-analysis perspective.
6. Risk level high if the topic involves security, compliance, financial decisions, or regulated domains."""


async def research_director(
    user_objective: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Interpret a user research objective and produce a structured plan.

    Args:
        user_objective: The raw user research request.
        model: Gemini model to use (reasoning tier).

    Returns:
        Dict with objective, scope, perspectives, completion_criteria,
        proposed_budget, and approval_recommendation.
    """
    if not is_llm_available():
        logger.warning("LLM unavailable — returning stub plan")
        return _stub_plan(user_objective)

    prompt = f"Research objective:\n\n{user_objective}"

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model or get_model_for_stage("scope_classify"),
            system_instruction=RESEARCH_DIRECTOR_INSTRUCTION,
            temperature=0.1,
        )
        result = parse_json_response(response)
        logger.info("research_director: plan generated for %r", user_objective[:80])
        return result if isinstance(result, dict) else _stub_plan(user_objective)
    except Exception as exc:
        logger.error("research_director failed: %s", exc)
        return _stub_plan(user_objective)


def _stub_plan(objective: str) -> dict[str, Any]:
    """Return a minimal stub plan when LLM is unavailable."""
    return {
        "objective": {
            "title": objective[:100] if objective else "Untitled Research",
            "primary_question": objective if objective else "",
            "decision_to_support": None,
            "intended_audience": ["technical"],
            "output_type": "technical_report",
            "desired_depth": "standard",
            "language": "en",
        },
        "scope": {
            "included_topics": [],
            "excluded_topics": [],
            "required_dimensions": [],
            "jurisdictions": [],
            "time_range": None,
            "risk_level": "low",
            "definitions": [],
            "assumptions": [{"text": "LLM unavailable — stub plan generated", "rationale": None}],
        },
        "proposed_perspectives": [
            {"name": "foundational", "purpose": "Basic facts and context", "required_questions": [], "preferred_source_types": [], "budget_weight": 1.0},
            {"name": "architecture", "purpose": "Implementation and design", "required_questions": [], "preferred_source_types": [], "budget_weight": 1.0},
            {"name": "skeptical", "purpose": "Challenge assumptions", "required_questions": [], "preferred_source_types": [], "budget_weight": 1.0},
            {"name": "enterprise", "purpose": "Operational implications", "required_questions": [], "preferred_source_types": [], "budget_weight": 1.0},
        ],
        "completion_criteria": [{"description": "LLM unavailable", "metric": "manual", "threshold": "N/A"}],
        "proposed_budget": {"searches": 20, "opened_sources": 10, "max_cost": 5.0, "max_wall_time_seconds": 600},
        "approval_recommendation": {"scope_approval_required": False, "outline_approval_required": False, "publication_approval_required": False, "rationale": "LLM unavailable"},
    }
