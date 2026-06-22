"""Durable audit helpers for enterprise governance."""

from __future__ import annotations

from typing import Any

from deep_research.storage.repositories import (
    list_audit_events,
    record_audit_event,
    verify_audit_chain,
)


async def record_event(
    run_id: str,
    event_type: str,
    principal: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Record one append-only audit event."""
    event = await record_audit_event(
        run_id=run_id,
        event_type=event_type,
        principal=principal,
        details=details,
    )
    return str(event["event_id"])


async def get_audit_trail(run_id: str) -> list[dict[str, Any]]:
    """Fetch all persisted audit events for a run."""
    return await list_audit_events(run_id)


async def verify_chain_integrity(run_id: str) -> bool:
    """Verify the persisted audit hash chain for a run."""
    return await verify_audit_chain(run_id)
