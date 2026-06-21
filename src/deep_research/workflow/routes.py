"""Workflow routing logic.

Determines edge transitions between nodes based on session state.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents.context import Context


def should_continue_research(state: dict[str, Any]) -> bool:
    """Check if the research loop should continue.

    Returns True if the stop evaluation says to continue,
    and there are still questions to process.
    """
    stop = state.get("app:stop_result", {})
    scheduler = state.get("app:scheduler_result", {})
    should_stop = stop.get("should_stop", True)
    if not isinstance(should_stop, bool):
        should_stop = True
    if should_stop:
        return False
    return scheduler.get("next_question_id") is not None


def has_blocking_findings(state: dict[str, Any]) -> bool:
    """Check if verification found blocking issues."""
    verify = state.get("app:verify_result", {})
    blocking_findings = verify.get("blocking_findings", 0)
    return isinstance(blocking_findings, int) and blocking_findings > 0


def was_approved(state: dict[str, Any], result_key: str) -> bool:
    """Check if a gate was approved."""
    result = state.get(result_key, {})
    approved = result.get("approved", True)
    return approved if isinstance(approved, bool) else True


def route_after_approve_plan(ctx: Context) -> str:
    """Route: approve_plan → scheduler or back to questions."""
    state = dict(ctx.session.state)
    if was_approved(state, "app:plan_approval_result"):
        return "scheduler_select"
    return "question_graph_build"


def route_after_stop(ctx: Context) -> str:
    """Route: stop_evaluate → outline or back to scheduler."""
    state = dict(ctx.session.state)
    if should_continue_research(state):
        return "scheduler_select"
    return "outline_build"


def route_after_approve_outline(ctx: Context) -> str:
    """Route: approve_outline → draft or back to outline."""
    state = dict(ctx.session.state)
    if was_approved(state, "app:outline_approval_result"):
        return "draft_generate"
    return "outline_build"


def route_after_verify(ctx: Context) -> str:
    """Route: verify_draft → repair or final_gate."""
    state = dict(ctx.session.state)
    if has_blocking_findings(state):
        return "repair_draft"
    return "final_gate_check"


def route_after_final_gate(ctx: Context) -> str:
    """Route: final_gate → render or repair."""
    state = dict(ctx.session.state)
    if was_approved(state, "app:final_gate_result"):
        return "render_output"
    return "repair_draft"
