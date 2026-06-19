"""Deterministic research frontier scheduler."""

from __future__ import annotations

from typing import Any

from deep_research.settings import get_settings

_QUESTION_TYPE_COST = {
    "implementation": 0.3,
    "causal": 0.4,
    "descriptive": 0.1,
    "definitional": 0.1,
    "comparative": 0.2,
    "mechanistic": 0.25,
    "security": 0.35,
    "failure-mode": 0.3,
    "failure_mode": 0.3,
    "counterfactual": 0.25,
    "evidence-challenge": 0.2,
    "evidence_challenge": 0.2,
    "contradiction-resolution": 0.25,
    "contradiction_resolution": 0.25,
    "normative": 0.2,
}

_MATERIALITY_SCORE = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}


def _question_id(question: dict[str, Any], index: int) -> str:
    return str(
        question.get("question_id")
        or question.get("id")
        or question.get("text")
        or f"question-{index}"
    )


def _normalize_dependencies(question: dict[str, Any]) -> set[str]:
    values = question.get("parent_question_ids", []) or question.get("dependencies", [])
    return {str(value) for value in values}


def _child_counts(questions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {_question_id(question, index): 0 for index, question in enumerate(questions)}
    for question in questions:
        for parent_id in _normalize_dependencies(question):
            counts[parent_id] = counts.get(parent_id, 0) + 1
    return counts


def _dependency_centrality(question: dict[str, Any], child_counts: dict[str, int], index: int) -> float:
    max_children = max(child_counts.values(), default=0)
    if max_children <= 0:
        return 0.0
    return child_counts.get(_question_id(question, index), 0) / max_children


def _uncertainty(question: dict[str, Any]) -> float:
    return 0.0 if question.get("status") == "resolved" else 1.0


def compute_priority(question: dict[str, Any], questions: list[dict[str, Any]], index: int) -> float:
    """Compute the weighted priority of a question."""
    settings = get_settings()
    weights = settings.scheduler
    child_counts = _child_counts(questions)

    materiality = question.get("materiality")
    materiality_score = _MATERIALITY_SCORE.get(str(materiality), float(question.get("materiality_score", 0.5)))
    risk = float(question.get("risk_score", 0.3))
    dependency = _dependency_centrality(question, child_counts, index)
    uncertainty = _uncertainty(question)
    novelty = float(question.get("novelty_score", 0.5))
    cost = _QUESTION_TYPE_COST.get(str(question.get("question_type", "")), 0.2)

    return (
        weights.w_materiality * materiality_score
        + weights.w_risk * risk
        + weights.w_dependency * dependency
        + weights.w_uncertainty * uncertainty
        + weights.w_novelty * novelty
        - weights.w_cost * cost
    )


def _questions_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_deps = _normalize_dependencies(left)
    right_deps = _normalize_dependencies(right)
    left_id = str(left.get("question_id", left.get("id", left.get("text", ""))))
    right_id = str(right.get("question_id", right.get("id", right.get("text", ""))))
    return bool(left_deps & right_deps) or left_id in right_deps or right_id in left_deps


def _parallel_groups(selected_questions: list[dict[str, Any]]) -> list[list[str]]:
    groups: list[list[str]] = []

    for question in selected_questions:
        question_name = str(question.get("question_id") or question.get("text") or "question")
        placed = False
        for group in groups:
            group_questions = [q for q in selected_questions if str(q.get("question_id") or q.get("text")) in group]
            if any(_questions_conflict(question, group_question) for group_question in group_questions):
                continue
            group.append(question_name)
            placed = True
            break
        if not placed:
            groups.append([question_name])

    return groups


def select_frontier_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the next top-k unresolved questions for execution."""
    settings = get_settings()
    prioritized: list[tuple[float, int, dict[str, Any]]] = []

    for index, question in enumerate(questions):
        if question.get("status") in {"resolved", "blocked", "deprioritized", "budget_exhausted"}:
            continue
        priority = compute_priority(question, questions, index)
        prioritized.append((priority, index, question))

    prioritized.sort(key=lambda item: item[0], reverse=True)
    top_k = max(1, settings.workflow.maximum_parallel_questions)
    selected = prioritized[:top_k]
    selected_questions = [question for _priority, _index, question in selected]

    priorities = {
        _question_id(question, index): round(priority, 4)
        for priority, index, question in prioritized
    }

    return {
        "selected_questions": selected_questions,
        "priorities": priorities,
        "parallel_groups": _parallel_groups(selected_questions),
    }
