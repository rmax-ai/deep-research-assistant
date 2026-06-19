"""Perspective budget tracking and section-local evidence filtering."""

from __future__ import annotations

from typing import Any

from deep_research.settings import get_settings


def initialize_perspective_budgets(perspectives: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Create initial per-perspective budgets."""
    settings = get_settings()
    defaults = settings.perspective_budget
    budgets: dict[str, dict[str, Any]] = {}

    for perspective in perspectives:
        name = str(perspective.get("name", "unknown"))
        weight = float(perspective.get("budget_weight", 1.0))
        budgets[name] = {
            "searches_remaining": max(1, int(defaults.searches * weight)),
            "tokens_remaining": max(1, int(defaults.tokens * weight)),
            "sources_remaining": max(1, int(defaults.sources * weight)),
            "status": "active",
        }

    return budgets


def enforce_perspective_budget(
    perspective_name: str,
    query_count: int,
    perspective_budgets: dict[str, dict[str, Any]],
    estimated_tokens: int = 0,
    estimated_sources: int = 0,
) -> dict[str, Any]:
    """Reject search plans that exceed perspective budget."""
    budget = perspective_budgets.setdefault(
        perspective_name,
        {"searches_remaining": 0, "tokens_remaining": 0, "sources_remaining": 0, "status": "budget_exhausted"},
    )

    if budget["status"] == "budget_exhausted":
        return {"accepted": False, "reason": "Perspective budget exhausted", "budget": budget}

    exceeds = (
        query_count > int(budget.get("searches_remaining", 0))
        or estimated_tokens > int(budget.get("tokens_remaining", 0))
        or estimated_sources > int(budget.get("sources_remaining", 0))
    )
    if exceeds:
        budget["status"] = "budget_exhausted"
        return {"accepted": False, "reason": "Search plan exceeds perspective budget", "budget": budget}

    budget["searches_remaining"] = int(budget.get("searches_remaining", 0)) - query_count
    budget["tokens_remaining"] = int(budget.get("tokens_remaining", 0)) - estimated_tokens
    budget["sources_remaining"] = int(budget.get("sources_remaining", 0)) - estimated_sources
    if (
        budget["searches_remaining"] <= 0
        or budget["tokens_remaining"] <= 0
        or budget["sources_remaining"] <= 0
    ):
        budget["status"] = "budget_exhausted"

    return {"accepted": True, "reason": "", "budget": budget}


def summarize_budget_remaining(perspective_budgets: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Aggregate remaining budget across perspectives."""
    return {
        "searches_remaining": float(sum(b.get("searches_remaining", 0) for b in perspective_budgets.values())),
        "tokens_remaining": float(sum(b.get("tokens_remaining", 0) for b in perspective_budgets.values())),
        "sources_remaining": float(sum(b.get("sources_remaining", 0) for b in perspective_budgets.values())),
    }


def filter_evidence_for_section(
    required_claim_ids: list[int | str],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only evidence fragments linked to the section's required claims."""
    evidence_indexes: set[str] = set()
    claim_keys = {str(value) for value in required_claim_ids}

    for index, claim in enumerate(claims):
        claim_id = str(claim.get("claim_id") or claim.get("id") or index)
        if claim_id not in claim_keys and str(index) not in claim_keys:
            continue
        evidence_indexes.update(str(evidence_id) for evidence_id in claim.get("evidence_ids", []))

    filtered: list[dict[str, Any]] = []
    for index, fragment in enumerate(evidence):
        fragment_id = str(fragment.get("evidence_id") or fragment.get("id") or index)
        if fragment_id in evidence_indexes or str(index) in evidence_indexes:
            filtered.append(fragment)

    return filtered
