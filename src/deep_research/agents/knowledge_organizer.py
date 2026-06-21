"""Knowledge Organizer Agent.

Maintains a conceptual topic graph spanning questions, claims, and evidence.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _slug(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if part)


async def knowledge_organizer(
    questions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    model: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    """Project research artifacts into a simple topic graph."""
    del model

    groups: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    claims_by_question: dict[str, list[str]] = defaultdict(list)
    evidence_by_question: dict[str, list[str]] = defaultdict(list)

    for claim in claims:
        question_id = str(claim.get("question_id", "unassigned"))
        claims_by_question[question_id].append(str(claim.get("claim_id", "")))

    for fragment in evidence:
        question_id = str(fragment.get("question_id", fragment.get("parent_question_id", "unassigned")))
        evidence_by_question[question_id].append(str(fragment.get("evidence_id", "")))

    perspective_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        perspective_groups[str(question.get("perspective", "general"))].append(question)

    for perspective, grouped_questions in perspective_groups.items():
        topic_id = f"topic-{_slug(perspective) or 'general'}"
        topic_node: dict[str, Any] = {
            "id": topic_id,
            "label": perspective.replace("_", " ").title(),
            "type": "perspective",
            "questions": [str(question.get("question_id", "")) for question in grouped_questions],
            "claims": [],
            "evidence": [],
        }
        question_group_id = f"{topic_id}-questions"
        groups[topic_id] = topic_node
        question_group: dict[str, Any] = {
            "id": question_group_id,
            "label": f"{topic_node['label']} Questions",
            "type": "question_group",
            "questions": topic_node["questions"],
            "claims": [],
            "evidence": [],
        }
        groups[question_group_id] = question_group
        edges.append({"source": topic_id, "target": question_group_id, "relation": "contains"})

        for question in grouped_questions:
            question_id = str(question.get("question_id", ""))
            question_claims = claims_by_question.get(question_id, [])
            question_evidence = evidence_by_question.get(question_id, [])
            concept_label = str(question.get("text") or question.get("topic") or question_id)
            concept_id = f"concept-{_slug(concept_label) or question_id}"
            groups[concept_id] = {
                "id": concept_id,
                "label": concept_label,
                "type": "concept",
                "questions": [question_id],
                "claims": question_claims,
                "evidence": question_evidence,
            }
            topic_node["claims"].extend(question_claims)
            topic_node["evidence"].extend(question_evidence)
            question_group["claims"].extend(question_claims)
            question_group["evidence"].extend(question_evidence)
            edges.append({"source": question_group_id, "target": concept_id, "relation": "groups"})

    return {
        "topic_nodes": list(groups.values()),
        "edges": edges,
        "version": 1,
    }
