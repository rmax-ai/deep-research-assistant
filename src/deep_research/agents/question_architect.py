"""Question Architect Agent — builds the initial question graph.

Generates typed research questions for each perspective,
establishes prerequisite dependencies, and assigns priorities.
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

FOLLOW_UP_INSTRUCTION = """You are a Question Architect generating evidence-conditioned follow-up questions.
Return ONLY a JSON object:
{
  "questions": [
    {
      "text": "string",
      "question_type": "implementation|causal|descriptive|comparative|evidence-challenge|contradiction-resolution|security|failure-mode",
      "parent_question_id": "string",
      "priority": 0.0,
      "rationale": "string"
    }
  ]
}"""


async def question_architect(
    perspectives: list[dict[str, Any]],
    scope: dict[str, Any] | None = None,
    model: str | None = None,
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
            model=model or get_model_for_stage("question_graph_build"),
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


def _tokenize(text: str) -> set[str]:
    return {
        token.strip(" ,.:;!?()[]{}\"'")
        for token in text.lower().split()
        if len(token.strip(" ,.:;!?()[]{}\"'")) >= 4
    }


def _is_duplicate_question(text: str, existing_questions: list[dict[str, Any]]) -> bool:
    candidate_tokens = _tokenize(text)
    if not candidate_tokens:
        return False
    for question in existing_questions:
        overlap = candidate_tokens & _tokenize(question.get("text", ""))
        if len(overlap) >= min(4, len(candidate_tokens)):
            return True
    return False


def _heuristic_follow_ups(
    evidence: list[dict[str, Any]],
    parent_question: dict[str, Any],
    existing_questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    follow_ups: list[dict[str, Any]] = []
    parent_id = str(
        parent_question.get("question_id")
        or parent_question.get("id")
        or parent_question.get("text", "parent-question")
    )
    parent_text = parent_question.get("text", "")

    for fragment in evidence[:3]:
        signal = (
            fragment.get("normalized_statement")
            or fragment.get("exact_excerpt")
            or fragment.get("source_id")
            or "the newly retrieved evidence"
        )
        source_hint = fragment.get("source_id") or fragment.get("title") or "this source"
        text = f"What does the evidence from {source_hint} imply about {parent_text}: {signal[:90]}?"
        if _is_duplicate_question(text, existing_questions + follow_ups):
            continue
        follow_ups.append({
            "text": text,
            "question_type": "evidence-challenge",
            "parent_question_id": parent_id,
            "priority": min(1.0, float(parent_question.get("priority", 0.5)) + 0.1),
            "rationale": f"Follow up on specific evidence signal: {signal[:120]}",
        })

    return follow_ups


async def generate_follow_ups(
    evidence: list[dict[str, Any]],
    parent_question: dict[str, Any],
    existing_questions: list[dict[str, Any]],
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Generate evidence-conditioned follow-up questions."""
    heuristic = _heuristic_follow_ups(evidence, parent_question, existing_questions)
    if not is_llm_available():
        return heuristic

    prompt = (
        f"Parent question: {parent_question}\n\n"
        f"Existing questions: {existing_questions}\n\n"
        f"Evidence: {evidence}"
    )

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model or get_model_for_stage("follow_up_question_generate"),
            system_instruction=FOLLOW_UP_INSTRUCTION,
            temperature=0.2,
        )
        result = parse_json_response(response, default={"questions": []})
        raw_questions = result.get("questions", [])
        follow_ups: list[dict[str, Any]] = []
        parent_id = str(
            parent_question.get("question_id")
            or parent_question.get("id")
            or parent_question.get("text", "parent-question")
        )
        for question in raw_questions:
            text = question.get("text", "")
            if not text or _is_duplicate_question(text, existing_questions + follow_ups):
                continue
            question["parent_question_id"] = parent_id
            follow_ups.append(question)
        return follow_ups or heuristic
    except Exception as exc:
        logger.error("generate_follow_ups failed: %s", exc)
        return heuristic
