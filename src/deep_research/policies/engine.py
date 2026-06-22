"""Policy evaluation engine for enterprise governance.

Evaluates {principal, action, resource, stage, risk_level} → {allow, deny, confirm}.
"""

from __future__ import annotations

import enum
from typing import Any


class PolicyDecision(enum.StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


# Role-to-tool allowlists
_ROLE_TOOLS: dict[str, set[str]] = {
    "anonymous": set(),
    "research_director": {"scope_classify", "perspective_generate"},
    "perspective_planner": {"perspective_generate"},
    "question_architect": {"question_graph_build"},
    "moderator": {"assess_frontier"},
    "query_planner": {"search_plan_create", "web_search", "url_retrieve"},
    "source_appraiser": {"source_policy_apply", "source_classify"},
    "evidence_curator": {"evidence_extract", "content_hash"},
    "claim_builder": {"claims_construct", "inference_create"},
    "counter_evidence": {"contradictions_search", "web_search"},
    "outline_architect": {"outline_build"},
    "section_writer": {"draft_generate", "read_claims"},
    "verifier": {"verify_draft", "check_entailment"},
    "executive_synthesizer": {"render_output"},
    "knowledge_organizer": {"concept_map", "topic_assignment"},
    "system": {"*"},  # Reserved for explicit internal operations only
}

# Stage-based tool reduction
_STAGE_REDUCTION: dict[str, set[str]] = {
    "drafting": {"web_search", "url_retrieve", "source_retrieve"},  # Writer shouldn't search
    "verification": {"web_search", "url_retrieve", "draft_generate"},  # Verifier shouldn't draft
    "completed": {"*"},  # No writes after completion
}


def evaluate_policy(
    principal: dict[str, Any],
    action: str,
    resource: str = "",
    context: dict[str, Any] | None = None,
) -> PolicyDecision:
    """Evaluate whether a principal can perform an action.

    Args:
        principal: Current principal context.
        action: The action being attempted (tool name).
        resource: The resource being accessed.
        context: Additional context (stage, risk_level, etc.).

    Returns:
        PolicyDecision: allow, deny, or confirm.
    """
    ctx = context or {}
    role = str(principal.get("agent_role", "system"))

    # System bypass only for explicit internal/bootstrap actions.
    if role == "system" and bool(ctx.get("internal")):
        return PolicyDecision.ALLOW

    # Role-based allowlist
    allowed = _ROLE_TOOLS.get(role, set())
    if "*" in allowed:
        return PolicyDecision.ALLOW
    if action not in allowed:
        return PolicyDecision.DENY

    # Stage-based reduction
    stage = str(ctx.get("stage", ""))
    if stage in _STAGE_REDUCTION:
        reduced = _STAGE_REDUCTION[stage]
        if "*" in reduced or action in reduced:
            return PolicyDecision.DENY

    # Write actions require confirmation
    write_actions = {
        "draft_generate", "render_output", "publish_report",
        "create_run", "update_scope", "publish_claim",
    }
    if action in write_actions:
        return PolicyDecision.CONFIRM

    return PolicyDecision.ALLOW


def reduce_tools_for_stage(
    agent_role: str,
    stage: str,
    available_tools: list[str],
) -> list[str]:
    """Reduce available tools based on workflow stage."""
    if agent_role == "system":
        return available_tools

    reduced = _STAGE_REDUCTION.get(stage, set())
    if "*" in reduced:
        return []
    return [t for t in available_tools if t not in reduced]
