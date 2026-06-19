"""Immutable audit log for enterprise governance.

Append-only event log with chain verification.
Events: run_created, scope_changed, question_created, query_executed,
source_retrieved, policy_decision, evidence_extracted, claim_created,
inference_created, contradiction_recorded, approval_requested,
approval_decided, model_invocation, tool_invocation, budget_exceeded,
report_generated, report_published.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


# In-memory audit store (replace with DB in production)
_audit_store: dict[str, list[dict[str, Any]]] = {}  # run_id → [events]


def reset_audit_log() -> None:
    """Reset audit store (for tests)."""
    _audit_store.clear()


def _hash_event(event: dict[str, Any], previous_hash: str | None = None) -> str:
    """Compute SHA-256 hash of event for chain verification."""
    payload = json.dumps(event, sort_keys=True, default=str)
    if previous_hash:
        payload = previous_hash + payload
    return hashlib.sha256(payload.encode()).hexdigest()


def record_event(
    run_id: str,
    event_type: str,
    principal: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Record an audit event. Returns event_id.

    Events are append-only — no modification by workflow agents.
    """
    store = _audit_store
    events = store.setdefault(run_id, [])

    previous_hash = events[-1].get("chain_hash") if events else None

    event = {
        "event_id": f"audit-{run_id}-{len(events):04d}",
        "timestamp": _utcnow().isoformat(),
        "event_type": event_type,
        "principal": principal or {},
        "run_id": run_id,
        "details": details or {},
    }
    event["chain_hash"] = _hash_event(event, previous_hash)

    events.append(event)
    return event["event_id"]


def get_audit_trail(run_id: str) -> list[dict[str, Any]]:
    """Get all audit events for a run."""
    return list(_audit_store.get(run_id, []))


def verify_chain_integrity(run_id: str) -> bool:
    """Verify the chain hash integrity of an audit trail."""
    events = _audit_store.get(run_id, [])
    if not events:
        return True

    for i, event in enumerate(events):
        prev_hash = events[i - 1].get("chain_hash") if i > 0 else None
        computed = _hash_event(
            {k: v for k, v in event.items() if k != "chain_hash"},
            prev_hash,
        )
        if computed != event.get("chain_hash"):
            return False
    return True
