"""Stopping condition evaluation for the iterative research loop."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from deep_research.settings import get_settings


class StoppingDecision(BaseModel):
    """Result of stopping condition evaluation."""

    should_stop: bool = False
    reasons: list[str] = Field(default_factory=list)
    unresolved_material_questions: list[str] = Field(default_factory=list)
    marginal_information_gain: float = 0.0
    evidence_diversity_score: float = 0.0
    primary_source_coverage: float = 0.0
    contradiction_resolution_rate: float = 0.0
    budget_remaining: dict[str, float] = Field(default_factory=dict)


def evaluate_stopping(
    coverage: dict[str, Any],
    budget_remaining: dict[str, Any],
    questions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    cycle_history: list[dict[str, Any]],
    elapsed_seconds: float = 0.0,
) -> StoppingDecision:
    """Evaluate whether the iterative research loop should stop."""
    settings = get_settings()
    decision = StoppingDecision(
        marginal_information_gain=float(coverage.get("marginal_information_gain", 0.0)),
        evidence_diversity_score=float(coverage.get("evidence_diversity_score", 0.0)),
        primary_source_coverage=float(coverage.get("primary_source_coverage", 0.0)),
        contradiction_resolution_rate=float(coverage.get("contradiction_resolution_rate", 0.0)),
        budget_remaining={key: float(value) for key, value in budget_remaining.items()},
    )

    unresolved_material_questions = [
        str(question.get("text", ""))
        for question in questions
        if question.get("status") != "resolved"
        and (question.get("materiality") in {"high", "critical"} or float(question.get("priority", 0.0)) >= 0.6)
    ]
    decision.unresolved_material_questions = unresolved_material_questions

    if not unresolved_material_questions and questions:
        decision.should_stop = True
        decision.reasons.append("All material questions resolved")

    minimum_primary_source_ratio = settings.research_policy.minimum_primary_source_ratio
    if decision.primary_source_coverage >= minimum_primary_source_ratio:
        decision.reasons.append("Primary source coverage target met")

    low_ig_window = settings.workflow.low_information_gain_cycle_threshold
    recent_info_gain = [
        float(cycle.get("information_gain", 0.0))
        for cycle in cycle_history[-low_ig_window:]
    ]
    if (
        len(recent_info_gain) >= low_ig_window
        and all(score < settings.workflow.information_gain_floor for score in recent_info_gain)
    ):
        decision.should_stop = True
        decision.reasons.append("Marginal information gain stayed below threshold for three cycles")

    searches_remaining = float(budget_remaining.get("searches_remaining", 0.0))
    tokens_remaining = float(budget_remaining.get("tokens_remaining", 0.0))
    sources_remaining = float(budget_remaining.get("sources_remaining", 0.0))
    if searches_remaining <= 0 or tokens_remaining <= 0 or sources_remaining <= 0:
        decision.should_stop = True
        decision.reasons.append("Budget exhausted")

    if elapsed_seconds >= settings.budget.maximum_wall_time_seconds:
        decision.should_stop = True
        decision.reasons.append("Maximum wall time reached")

    if len(cycle_history) >= settings.workflow.max_cycles:
        decision.should_stop = True
        decision.reasons.append("Maximum cycle count reached")

    material_claim_ids = {
        str(claim.get("claim_id") or claim.get("id") or index)
        for index, claim in enumerate(claims)
        if claim.get("materiality") in {"high", "critical"}
    }
    claims_with_contradiction_search = {
        str(claim_id)
        for contradiction in contradictions
        for claim_id in contradiction.get("claim_ids", [])
    }
    if material_claim_ids and material_claim_ids.issubset(claims_with_contradiction_search):
        decision.reasons.append("Contradiction search complete for material claims")

    if (
        decision.primary_source_coverage >= minimum_primary_source_ratio
        and not unresolved_material_questions
        and (not material_claim_ids or material_claim_ids.issubset(claims_with_contradiction_search))
    ):
        decision.should_stop = True

    return decision
