"""Stopping condition evaluation.

Determines when the research loop should terminate based on
information gain, coverage, budget, and contradiction resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoppingDecision:
    """Result of stopping condition evaluation."""

    should_stop: bool = False
    reasons: list[str] = field(default_factory=list)
    unresolved_material_questions: list[str] = field(default_factory=list)
    marginal_information_gain: float = 0.0
    evidence_diversity_score: float = 0.0
    primary_source_coverage: float = 0.0
    contradiction_resolution_rate: float = 0.0
    budget_remaining: dict[str, float] = field(default_factory=dict)


def evaluate_stopping(
    coverage: dict[str, Any],
    budget: dict[str, Any],
    cycle_count: int,
    max_cycles: int = 10,
) -> StoppingDecision:
    """Evaluate whether the research loop should stop.

    Args:
        coverage: Coverage metrics from the coverage_calculate node.
        budget: Current budget state.
        cycle_count: Number of research cycles completed.
        max_cycles: Hard limit on research cycles.

    Returns:
        StoppingDecision with should_stop and rationale.
    """
    decision = StoppingDecision()

    # Hard cycle limit
    if cycle_count >= max_cycles:
        decision.should_stop = True
        decision.reasons.append(f"Maximum cycles ({max_cycles}) reached")
        return decision

    # Budget exhaustion
    searches_remaining = budget.get("searches_remaining", 0)
    if searches_remaining <= 0:
        decision.should_stop = True
        decision.reasons.append("Search budget exhausted")
        return decision

    # Information gain threshold
    info_gain = coverage.get("information_gain", 0.0)
    info_gain_threshold = coverage.get("info_gain_threshold", 0.01)
    if info_gain < info_gain_threshold and cycle_count > 0:
        decision.should_stop = True
        decision.reasons.append(
            f"Information gain ({info_gain:.4f}) below threshold ({info_gain_threshold})"
        )

    # Primary source coverage
    primary_coverage = coverage.get("primary_source_coverage", 0.0)
    min_coverage = coverage.get("min_primary_coverage", 0.5)
    if primary_coverage >= min_coverage and decision.reasons:
        decision.reasons.append(
            f"Primary source coverage ({primary_coverage:.2f}) meets minimum ({min_coverage})"
        )

    # All material questions resolved
    unresolved = coverage.get("unresolved_material_questions", [])
    if not unresolved and cycle_count > 0:
        if not decision.should_stop:
            decision.should_stop = True
        decision.reasons.append("All material questions resolved")

    decision.marginal_information_gain = info_gain
    decision.primary_source_coverage = primary_coverage
    decision.contradiction_resolution_rate = coverage.get(
        "contradiction_resolution_rate", 0.0
    )
    decision.unresolved_material_questions = unresolved

    return decision
