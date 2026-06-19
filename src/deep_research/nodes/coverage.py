"""Deterministic coverage and information-gain metrics."""

from __future__ import annotations

from typing import Any

from deep_research.settings import get_settings


def _moving_average(values: list[float], window: int = 3) -> float:
    if not values:
        return 0.0
    sample = values[-window:]
    return sum(sample) / len(sample)


def calculate_coverage(
    cycle_history: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute iterative coverage and information-gain metrics."""
    settings = get_settings()
    weights = settings.information_gain

    prior_cycle = cycle_history[-1] if cycle_history else {}
    seen_claim_ids = {
        str(claim_id)
        for cycle in cycle_history
        for claim_id in cycle.get("new_claim_ids", [])
    }
    seen_clusters = {
        str(cluster_id)
        for cycle in cycle_history
        for cluster_id in cycle.get("new_evidence_clusters", [])
    }

    current_claim_ids = {
        str(claim.get("claim_id") or claim.get("id") or claim.get("text"))
        for claim in claims
    }
    novel_claims = current_claim_ids - seen_claim_ids

    current_clusters = {
        str(
            fragment.get("source_cluster")
            or fragment.get("source_id")
            or fragment.get("source_url")
            or fragment.get("title")
        )
        for fragment in evidence
    }
    novel_clusters = {cluster for cluster in current_clusters if cluster and cluster not in seen_clusters}

    resolved_questions = [
        question for question in questions
        if question.get("status") == "resolved"
        and question.get("resolved_in_cycle") is not False
    ]
    resolved_contradictions = [
        contradiction for contradiction in contradictions
        if str(contradiction.get("resolution_status", "")).startswith("resolved")
    ]

    duplicated_evidence = max(0, len(evidence) - len(current_clusters))
    info_gain = (
        weights.alpha_novel_claims * len(novel_claims)
        + weights.beta_novel_evidence * len(novel_clusters)
        + weights.gamma_resolved_gaps * len(resolved_questions)
        + weights.delta_resolved_contradictions * len(resolved_contradictions)
        - weights.lambda_duplication * duplicated_evidence
    )

    primary_sources = [
        source for source in sources
        if source.get("is_primary") or source.get("source_type") in {"official", "primary", "repository"}
    ]
    evidence_diversity_score = min(1.0, len(current_clusters) / max(1, len(evidence)))
    contradiction_resolution_rate = (
        len(resolved_contradictions) / len(contradictions) if contradictions else 1.0
    )
    unresolved_material_questions = [
        str(question.get("text", ""))
        for question in questions
        if question.get("status") != "resolved"
        and (question.get("materiality") in {"high", "critical"} or float(question.get("priority", 0.0)) >= 0.6)
    ]

    history_scores = [float(cycle.get("information_gain", 0.0)) for cycle in cycle_history]
    history_scores.append(info_gain)
    moving_average = _moving_average(history_scores)

    cycle_summary = {
        "cycle": int(prior_cycle.get("cycle", 0)) + 1,
        "information_gain": info_gain,
        "new_claim_ids": sorted(novel_claims),
        "new_evidence_clusters": sorted(novel_clusters),
        "resolved_question_ids": [
            str(question.get("question_id") or question.get("text"))
            for question in resolved_questions
        ],
        "resolved_contradiction_ids": [
            str(contradiction.get("contradiction_id") or contradiction.get("id"))
            for contradiction in resolved_contradictions
        ],
        "primary_source_coverage": len(primary_sources) / len(sources) if sources else 0.0,
        "evidence_diversity_score": evidence_diversity_score,
        "contradiction_resolution_rate": contradiction_resolution_rate,
        "novelty_score": moving_average,
    }

    return {
        "information_gain": info_gain,
        "marginal_information_gain": moving_average,
        "primary_source_coverage": cycle_summary["primary_source_coverage"],
        "evidence_diversity_score": evidence_diversity_score,
        "contradiction_resolution_rate": contradiction_resolution_rate,
        "unresolved_material_questions": unresolved_material_questions,
        "cycle_summary": cycle_summary,
    }
