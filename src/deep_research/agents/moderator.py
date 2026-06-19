"""Research Moderator Agent for iterative loop rebalancing."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from deep_research.agents import generate_structured, is_llm_available, parse_json_response

logger = logging.getLogger(__name__)

MODERATOR_INSTRUCTION = """You are a Research Moderator for an iterative research system.
Your role is to detect stagnation, imbalance, and missing adversarial evidence, then rebalance the research frontier.

Return ONLY a JSON object with:
{
  "rebalance_actions": [
    {"type": "reprioritize|add_counter_evidence|introduce_question_type|rebalance_perspective",
     "target": "string",
     "rationale": "string"}
  ],
  "adjusted_priorities": {"question_id_or_text": 0.0},
  "stagnation_detected": true
}"""


def _detect_stagnation(cycle_history: list[dict[str, Any]]) -> bool:
    recent = cycle_history[-3:]
    if len(recent) < 3:
        return False
    return all(float(cycle.get("novelty_score", cycle.get("information_gain", 0.0))) < 0.1 for cycle in recent)


def _missing_adversarial_evidence(claims: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contradicted_claim_ids = {
        str(claim_id)
        for contradiction in contradictions
        for claim_id in contradiction.get("claim_ids", [])
    }
    missing: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        claim_id = str(claim.get("claim_id") or claim.get("id") or index)
        if claim.get("materiality") not in {"high", "critical"}:
            continue
        if claim_id in contradicted_claim_ids or claim.get("counter_evidence_ids"):
            continue
        missing.append(claim)
    return missing


def _perspective_imbalance(questions: list[dict[str, Any]]) -> tuple[bool, str | None]:
    active = [
        str(question.get("perspective", "unknown"))
        for question in questions
        if question.get("status") in {None, "pending", "in_progress", "resolved"}
    ]
    if not active:
        return False, None
    counts = Counter(active)
    perspective, count = counts.most_common(1)[0]
    return (count / len(active)) > 0.6, perspective


def _heuristic_result(state_data: dict[str, Any]) -> dict[str, Any]:
    questions = state_data.get("questions", [])
    claims = state_data.get("claims", [])
    contradictions = state_data.get("contradictions", [])
    cycle_history = state_data.get("recent_cycle_history", [])

    rebalance_actions: list[dict[str, str]] = []
    adjusted_priorities: dict[str, float] = {}

    stagnation_detected = _detect_stagnation(cycle_history)
    if stagnation_detected:
        rebalance_actions.append({
            "type": "introduce_question_type",
            "target": "evidence-challenge",
            "rationale": "Three consecutive low-novelty cycles indicate stagnation.",
        })

    for claim in _missing_adversarial_evidence(claims, contradictions):
        target = str(claim.get("claim_id") or claim.get("text", "claim"))
        rebalance_actions.append({
            "type": "add_counter_evidence",
            "target": target,
            "rationale": "High-materiality claim lacks counter-evidence coverage.",
        })

    imbalanced, dominant_perspective = _perspective_imbalance(questions)
    if imbalanced and dominant_perspective:
        rebalance_actions.append({
            "type": "rebalance_perspective",
            "target": dominant_perspective,
            "rationale": "One perspective is consuming more than 60% of attention.",
        })
        for index, question in enumerate(questions):
            key = str(question.get("question_id") or question.get("id") or question.get("text") or index)
            base_priority = float(question.get("priority", 0.5))
            if question.get("perspective") == dominant_perspective:
                adjusted_priorities[key] = round(max(0.0, base_priority - 0.15), 3)
            else:
                adjusted_priorities[key] = round(min(1.0, base_priority + 0.1), 3)

    return {
        "rebalance_actions": rebalance_actions,
        "adjusted_priorities": adjusted_priorities,
        "stagnation_detected": stagnation_detected,
    }


async def moderator(
    state_data: dict[str, Any],
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Assess the research frontier and suggest rebalancing actions."""
    heuristic = _heuristic_result(state_data)
    if not is_llm_available():
        return heuristic

    prompt = (
        f"Questions: {state_data.get('questions', [])}\n\n"
        f"Claims: {state_data.get('claims', [])}\n\n"
        f"Contradictions: {state_data.get('contradictions', [])}\n\n"
        f"Recent cycle history: {state_data.get('recent_cycle_history', [])}"
    )

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model,
            system_instruction=MODERATOR_INSTRUCTION,
            temperature=0.1,
        )
        result = parse_json_response(response, default={})
        return {
            "rebalance_actions": result.get("rebalance_actions", heuristic["rebalance_actions"]),
            "adjusted_priorities": result.get("adjusted_priorities", heuristic["adjusted_priorities"]),
            "stagnation_detected": bool(result.get("stagnation_detected", heuristic["stagnation_detected"])),
        }
    except Exception as exc:
        logger.error("moderator failed: %s", exc)
        return heuristic
