"""Deterministic validation node.

Validates that research state matches expected schemas at each
workflow transition point.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Minimum required fields per workflow stage
STAGE_REQUIREMENTS: dict[str, list[str]] = {
    "scope_classify": [],
    "perspective_generate": ["app:scope_result"],
    "question_graph_build": ["app:perspective_result"],
    "approve_plan": ["app:question_graph_result"],
    "scheduler_select": ["app:plan_approval_result"],
    "search_plan_create": ["app:scheduler_result"],
    "source_retrieve": ["app:search_plan_result"],
    "source_policy_apply": ["app:source_retrieval_result"],
    "evidence_extract": ["app:source_policy_result"],
    "claims_construct": ["app:evidence_result"],
    "contradictions_search": ["app:claims_result"],
    "coverage_calculate": ["app:contradictions_result"],
    "stop_evaluate": ["app:coverage_result"],
    "outline_build": ["app:stop_result"],
    "approve_outline": ["app:outline_result"],
    "draft_generate": ["app:outline_approval_result"],
    "verify_draft": ["app:draft_result"],
    "repair_draft": ["app:verify_result"],
    "final_gate_check": ["app:verify_result"],
    "render_output": ["app:final_gate_result"],
}


def validate_stage_inputs(
    node_name: str,
    state: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that required state keys exist for a node.

    Args:
        node_name: The name of the node being entered.
        state: Current session state dict.

    Returns:
        (is_valid, list_of_missing_keys)
    """
    required = STAGE_REQUIREMENTS.get(node_name, [])
    missing = [k for k in required if k not in state or state[k] is None]
    is_valid = len(missing) == 0

    if not is_valid:
        logger.warning(
            "validation failed for %s: missing %s",
            node_name,
            missing,
        )

    return is_valid, missing


def validate_result_structure(
    node_name: str,
    result: dict[str, Any],
) -> bool:
    """Validate that a node result has the expected structure.

    Every node result must have at minimum a 'status' field.
    """
    if "status" not in result:
        logger.error("node %s result missing 'status' field", node_name)
        return False
    return True
