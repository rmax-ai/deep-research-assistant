"""Question Architect Agent — builds the initial question graph.

Generates typed research questions for each perspective,
establishes prerequisite dependencies, and assigns priorities.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import generate_structured, is_llm_available, parse_json_response

logger = logging.getLogger(__name__)

QUESTION_ARCHITECT_INSTRUCTION = """You are a Question Architect for an enterprise research system.
Your role is to generate a structured set of research questions that will guide evidence collection.

## Your Task
Given research perspectives, generate questions for each perspective.

## Question Types (use these labels)
- **definitional**: What is X? How is Y defined?
- **descriptive**: How does X work? What are the components?
- **mechanistic**: What is the mechanism by which X causes Y?
- **comparative**: How does X compare to Y?
- **causal**: Does X cause Y? What is the evidence?
- **implementation**: How is X implemented? What are the code/details?
- **security**: What are the security properties of X?
- **failure-mode**: What can go wrong with X? What are known issues?
- **counterfactual**: What if X were different?
- **evidence-challenge**: Is the evidence for X actually reliable?
- **contradiction-resolution**: How to resolve conflicting evidence about X?
- **normative**: Should we use X? What is the best approach?

## Question Generation Rules
1. Start with broad prerequisite questions (definitional, descriptive)
2. Create dependency edges: foundational questions before specific ones
3. Include questions that could FALSIFY likely conclusions
4. Label every question with its type
5. Mark high-risk questions (involving security, compliance, financial decisions)
6. Do NOT answer the questions — only formulate them
7. Generate 3-5 questions per perspective minimum

## For each question provide
- text: the full question text
- question_type: one of the types above
- perspective: which perspective this belongs to
- parent_question_ids: list of prerequisite question indices (0-based) that must be answered first
- rationale: why this question matters
- priority: 0.0-1.0 (higher = more important)
- risk_score: 0.0-1.0 (higher = more sensitive/risky to get wrong)
- novelty_score: 0.0-1.0 (expected to produce new information)

## Output Format
Return ONLY a JSON object. No markdown, no explanation.

{
  "questions": [
    {
      "text": "string",
      "question_type": "definitional|descriptive|mechanistic|...",
      "perspective": "string (must match a perspective name)",
      "parent_question_ids": [0, 2],
      "rationale": "string",
      "priority": 0.8,
      "risk_score": 0.3,
      "novelty_score": 0.5
    },
    ...
  ]
}"""


async def question_architect(
    perspectives: list[dict[str, Any]],
    scope: dict[str, Any] | None = None,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Generate a question graph from research perspectives.

    Args:
        perspectives: List of perspective dicts from Perspective Planner.
        scope: Optional scope for additional context.
        model: Gemini model (fast tier OK for question generation).

    Returns:
        Dict with 'questions' list.
    """
    if not is_llm_available():
        logger.warning("LLM unavailable — returning stub questions")
        return _stub_questions(perspectives)

    perspective_text = "\n".join(
        f"- {p.get('name', 'unknown')}: {p.get('purpose', '')}"
        for p in perspectives
    )

    prompt = f"""Research perspectives:
{perspective_text}

Scope context:
{scope or 'Not provided'}

Generate research questions for these perspectives."""

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model,
            system_instruction=QUESTION_ARCHITECT_INSTRUCTION,
            temperature=0.2,
        )
        result = parse_json_response(response, default={"questions": []})
        questions = result.get("questions", [])
        logger.info("question_architect: generated %d questions", len(questions))
        return {"questions": questions}
    except Exception as exc:
        logger.error("question_architect failed: %s", exc)
        return _stub_questions(perspectives)


def _stub_questions(perspectives: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stub questions for each perspective."""
    questions = []
    for i, p in enumerate(perspectives):
        name = p.get("name", f"perspective_{i}")
        purpose = p.get("purpose", "")
        questions.append({
            "text": f"What are the core facts about {name}?",
            "question_type": "definitional",
            "perspective": name,
            "parent_question_ids": [],
            "rationale": f"Foundational question for {purpose}",
            "priority": 0.9,
            "risk_score": 0.1,
            "novelty_score": 0.3,
        })
    return {"questions": questions}
