"""Identity context and principal propagation for enterprise governance.

Every tool invocation carries: tenant_id, user_id, run_id, node_path,
agent_role, purpose, policy_decision_id, delegated_scopes.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Principal(TypedDict, total=False):
    tenant_id: str
    user_id: str
    run_id: str
    node_path: str
    agent_role: str
    purpose: str
    policy_decision_id: str | None
    delegated_scopes: list[str]


_DEFAULT_PRINCIPAL: Principal = {
    "tenant_id": "default",
    "user_id": "system",
    "run_id": "",
    "node_path": "",
    "agent_role": "system",
    "purpose": "research",
    "policy_decision_id": None,
    "delegated_scopes": [],
}


def get_current_principal(state: dict[str, Any] | None = None) -> Principal:
    """Get current principal from session state, or default."""
    if state is None:
        from deep_research.workflow.state import get_state
        state = get_state()
    stored = state.get("app:principal")
    if stored and isinstance(stored, dict):
        return {
            "tenant_id": str(stored.get("tenant_id", "default")),
            "user_id": str(stored.get("user_id", "system")),
            "run_id": str(stored.get("run_id", "")),
            "node_path": str(stored.get("node_path", "")),
            "agent_role": str(stored.get("agent_role", "system")),
            "purpose": str(stored.get("purpose", "research")),
            "policy_decision_id": stored.get("policy_decision_id"),
            "delegated_scopes": list(stored.get("delegated_scopes", [])),
        }
    return dict(_DEFAULT_PRINCIPAL)


def propagate_principal(
    principal: Principal,
    node_path: str,
    agent_role: str,
    purpose: str | None = None,
) -> Principal:
    """Create a derived principal for a sub-node or sub-agent.

    Delegation does not expand permissions — identity is preserved.
    """
    return {
        "tenant_id": principal["tenant_id"],
        "user_id": principal["user_id"],
        "run_id": principal["run_id"],
        "node_path": node_path,
        "agent_role": agent_role,
        "purpose": purpose or principal.get("purpose", "research"),
        "policy_decision_id": principal.get("policy_decision_id"),
        "delegated_scopes": list(principal.get("delegated_scopes", [])),
    }


def set_principal(state: dict[str, Any], principal: Principal) -> None:
    """Store principal in session state."""
    state["app:principal"] = dict(principal)
