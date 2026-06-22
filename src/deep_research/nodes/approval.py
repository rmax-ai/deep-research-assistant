"""Approval gate evaluation for collaborative review stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApprovalGate(BaseModel):
    """Runtime approval gate state."""

    gate: str
    required: bool
    display_data: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"


_RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _risk_requires(current_risk: str, configured_threshold: str) -> bool:
    if configured_threshold == "never":
        return False
    if configured_threshold == "all":
        return True
    return _RISK_ORDER.get(current_risk, 1) >= _RISK_ORDER.get(configured_threshold, 2)


async def check_gate(gate: str, run_state: dict[str, Any], settings: Any) -> ApprovalGate:
    """Compute whether a human approval gate is required."""
    scope = run_state.get("app:scope", {})
    objective = run_state.get("app:objective", {})
    current_risk = str(scope.get("risk_level", "medium"))
    approval_recommendation = run_state.get("app:research_plan", {}).get("approval_recommendation", {})
    source_constraints = scope.get("source_constraints", {}) if isinstance(scope, dict) else {}
    blocked_domains = source_constraints.get("blocked_domains", []) if isinstance(source_constraints, dict) else []

    if gate == "A":
        required = _risk_requires(current_risk, settings.approvals.scope_required_for_risk) or bool(
            approval_recommendation.get("scope_approval_required")
        )
        display_data = {
            "objective": objective,
            "scope": scope,
            "risk_level": current_risk,
            "restricted_corpora": blocked_domains,
            "proposed_perspectives": run_state.get("app:proposed_perspectives", []),
            "budget": run_state.get("app:research_plan", {}).get("proposed_budget", {}),
        }
    elif gate == "B":
        required = _risk_requires(current_risk, settings.approvals.plan_required_for_risk)
        display_data = {
            "questions": run_state.get("app:questions", []),
            "perspectives": run_state.get("app:perspectives", []),
            "source_strategy": run_state.get("app:research_plan", {}).get("source_strategy", {}),
            "budget": run_state.get("app:research_plan", {}).get("proposed_budget", {}),
            "exclusions": scope.get("excluded_topics", []),
            "limitations": run_state.get("app:research_plan", {}).get("limitations", []),
        }
    elif gate == "C":
        required = _risk_requires(current_risk, settings.approvals.outline_required_for_risk) or bool(
            approval_recommendation.get("outline_approval_required")
        )
        display_data = {
            "outline": run_state.get("app:outline", {}),
            "principal_claims": run_state.get("app:claims", [])[:10],
            "confidence_summary": run_state.get("app:coverage", {}),
            "source_mix": {
                "sources": len(run_state.get("app:sources", [])),
                "evidence": len(run_state.get("app:evidence", [])),
            },
            "contradictions": run_state.get("app:contradictions", []),
            "unresolved_questions": [
                q for q in run_state.get("app:questions", []) if q.get("status") != "resolved"
            ][:10],
        }
    elif gate == "D":
        required = bool(approval_recommendation.get("publication_approval_required")) or bool(
            settings.approvals.publication_required_for_external
            and objective.get("intended_audience")
        )
        display_data = {
            "final_claims": run_state.get("app:claims", [])[:10],
            "recommendations": run_state.get("app:drafts", []),
            "verification": run_state.get("app:verification", {}),
            "risk_indicators": {
                "risk_level": current_risk,
                "blocking_findings": run_state.get("app:verification", {}).get("blocking_findings", 0),
            },
            "report_preview": run_state.get("app:final_report_preview", ""),
        }
    else:
        raise ValueError(f"Unknown gate: {gate}")

    decisions = run_state.setdefault("app:approval_decisions", {})
    # Check for pre-set approval inputs (from tests or API)
    inputs = run_state.get("app:approval_inputs", {})
    prior_status = inputs.get(gate, {}).get("status") or decisions.get(gate, {}).get("status", "pending")
    status = prior_status if required else "not_required"

    approval = ApprovalGate(
        gate=gate,
        required=required,
        display_data=display_data,
        status=status,
    )
    decisions.setdefault(gate, approval.model_dump())
    return approval
