"""Repository helpers for persisted runtime state."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from deep_research.storage.database import get_session
from deep_research.storage.models import (
    ApprovalDecisionRecord,
    AuditEventRecord,
    ResearchRunRecord,
    WorkflowCheckpointRecord,
    WorkflowNodeExecutionRecord,
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _record_to_run_data(record: ResearchRunRecord) -> dict[str, Any]:
    state = _as_dict(record.state_json)
    return {
        "run_id": record.run_id,
        "session_id": record.session_id,
        "status": record.status,
        "phase": record.phase,
        "report": record.report,
        "event_count": record.event_count,
        "events": [],
        "state": state,
        "approvals": _as_dict(record.approvals_json),
        "interventions": _as_list(record.interventions_json),
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "updated_at": record.updated_at,
        "error": record.error,
        "objective": _as_dict(record.objective_json),
        "scope": _as_dict(record.scope_json),
        "questions_count": record.questions_count,
        "claims_count": record.claims_count,
        "sources_count": record.sources_count,
        "tenant_id": record.tenant_id,
        "user_id": record.user_id,
        "workflow_version": record.workflow_version,
        "current_node": record.current_node,
        "awaiting_approval_gate": record.awaiting_approval_gate,
        "resume_from_checkpoint_id": record.resume_from_checkpoint_id,
        "retry_count": record.retry_count,
        "last_policy_decision_id": record.last_policy_decision_id,
    }


def _apply_run_data(record: ResearchRunRecord, run_data: dict[str, Any]) -> None:
    record.session_id = str(run_data.get("session_id", ""))
    record.status = str(run_data.get("status", "queued"))
    record.phase = str(run_data.get("phase", "planning"))
    record.created_at = str(run_data.get("created_at", ""))
    record.started_at = run_data.get("started_at")
    record.completed_at = run_data.get("completed_at")
    updated_at = run_data.get("updated_at")
    record.updated_at = str(updated_at) if updated_at is not None else _utcnow()
    record.tenant_id = str(run_data.get("tenant_id", "default"))
    record.user_id = str(run_data.get("user_id", "api_user"))
    record.objective_json = _as_dict(run_data.get("objective"))
    record.scope_json = _as_dict(run_data.get("scope"))
    record.state_json = _as_dict(run_data.get("state"))
    record.report = str(run_data.get("report", ""))
    record.event_count = int(run_data.get("event_count", 0))
    error = run_data.get("error")
    record.error = str(error) if error is not None else None
    record.approvals_json = _as_dict(run_data.get("approvals"))
    record.interventions_json = _as_list(run_data.get("interventions"))
    record.questions_count = int(run_data.get("questions_count", 0))
    record.claims_count = int(run_data.get("claims_count", 0))
    record.sources_count = int(run_data.get("sources_count", 0))
    record.workflow_version = str(run_data.get("workflow_version", "1.0.0"))
    current_node = run_data.get("current_node")
    record.current_node = str(current_node) if current_node else None
    awaiting_gate = run_data.get("awaiting_approval_gate")
    record.awaiting_approval_gate = str(awaiting_gate) if awaiting_gate else None
    checkpoint_id = run_data.get("resume_from_checkpoint_id")
    record.resume_from_checkpoint_id = str(checkpoint_id) if checkpoint_id else None
    record.retry_count = int(run_data.get("retry_count", 0))
    last_policy = run_data.get("last_policy_decision_id")
    record.last_policy_decision_id = str(last_policy) if last_policy else None


async def create_run(run_data: dict[str, Any]) -> dict[str, Any]:
    """Create or overwrite a persisted run row."""
    async for session in get_session():
        record = await session.get(ResearchRunRecord, str(run_data["run_id"]))
        if record is None:
            record = ResearchRunRecord(run_id=str(run_data["run_id"]))
            session.add(record)
        _apply_run_data(record, run_data)
        await session.commit()
        await session.refresh(record)
        return _record_to_run_data(record)
    raise RuntimeError("database session unavailable")


async def get_run(run_id: str) -> dict[str, Any] | None:
    """Fetch one run by id."""
    async for session in get_session():
        result = await session.execute(
            select(ResearchRunRecord).where(ResearchRunRecord.run_id == run_id)
        )
        record = result.scalar_one_or_none()
        return _record_to_run_data(record) if record is not None else None
    raise RuntimeError("database session unavailable")


async def list_runs(*, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    """List persisted runs, optionally filtered by status."""
    async for session in get_session():
        stmt = select(ResearchRunRecord)
        if statuses:
            stmt = stmt.where(ResearchRunRecord.status.in_(statuses))
        result = await session.execute(stmt.order_by(ResearchRunRecord.created_at))
        records = result.scalars().all()
        return [_record_to_run_data(record) for record in records]
    raise RuntimeError("database session unavailable")


async def update_run(run_id: str, run_data: dict[str, Any]) -> dict[str, Any]:
    """Update a persisted run row."""
    payload = dict(run_data)
    payload["run_id"] = run_id
    return await create_run(payload)


async def update_run_runtime(
    run_id: str,
    *,
    state: dict[str, Any] | None = None,
    status: str | None = None,
    phase: str | None = None,
    current_node: str | None = None,
    awaiting_approval_gate: str | None = None,
    resume_from_checkpoint_id: str | None = None,
    retry_count: int | None = None,
    last_policy_decision_id: str | None = None,
    workflow_version: str | None = None,
    completed_at: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Update runtime-facing run metadata without rebuilding the entire payload."""
    existing = await get_run(run_id)
    if existing is None:
        raise RuntimeError(f"Run {run_id} not found")
    payload = dict(existing)
    if state is not None:
        payload["state"] = state
    if status is not None:
        payload["status"] = status
    if phase is not None:
        payload["phase"] = phase
    if current_node is not None:
        payload["current_node"] = current_node
    if awaiting_approval_gate is not None or awaiting_approval_gate == "":
        payload["awaiting_approval_gate"] = awaiting_approval_gate or None
    if resume_from_checkpoint_id is not None or resume_from_checkpoint_id == "":
        payload["resume_from_checkpoint_id"] = resume_from_checkpoint_id or None
    if retry_count is not None:
        payload["retry_count"] = retry_count
    if last_policy_decision_id is not None or last_policy_decision_id == "":
        payload["last_policy_decision_id"] = last_policy_decision_id or None
    if workflow_version is not None:
        payload["workflow_version"] = workflow_version
    if completed_at is not None:
        payload["completed_at"] = completed_at
    if error is not None:
        payload["error"] = error
    payload["updated_at"] = _utcnow()
    if state is not None:
        payload["objective"] = state.get("app:objective", payload.get("objective", {})) or payload.get("objective", {})
        payload["scope"] = state.get("app:scope", payload.get("scope", {})) or payload.get("scope", {})
        payload["approvals"] = state.get("app:approval_decisions", payload.get("approvals", {}))
        payload["interventions"] = list(state.get("app:pending_interventions", payload.get("interventions", [])))
        payload["questions_count"] = len(state.get("app:questions", []))
        payload["claims_count"] = len(state.get("app:claims", []))
        payload["sources_count"] = len(state.get("app:sources", []))
        payload["report"] = state.get("app:final_report", payload.get("report", ""))
    return await update_run(run_id, payload)


async def create_workflow_checkpoint(
    *,
    run_id: str,
    node_name: str,
    node_path: str,
    workflow_version: str,
    logical_input_hash: str,
    state: dict[str, Any],
    status: str = "completed",
) -> dict[str, Any]:
    """Persist a workflow checkpoint."""
    checkpoint_id = f"{run_id}:{node_name}:{logical_input_hash}:{int(datetime.now(UTC).timestamp() * 1000)}"
    async for session in get_session():
        record = WorkflowCheckpointRecord(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            node_name=node_name,
            node_path=node_path,
            workflow_version=workflow_version,
            logical_input_hash=logical_input_hash,
            state_json=_as_dict(state),
            status=status,
            created_at=_utcnow(),
        )
        session.add(record)
        await session.commit()
        return {
            "checkpoint_id": record.checkpoint_id,
            "run_id": record.run_id,
            "node_name": record.node_name,
            "node_path": record.node_path,
            "workflow_version": record.workflow_version,
            "logical_input_hash": record.logical_input_hash,
            "state": _as_dict(record.state_json),
            "status": record.status,
            "created_at": record.created_at,
        }
    raise RuntimeError("database session unavailable")


async def get_latest_checkpoint(run_id: str) -> dict[str, Any] | None:
    """Fetch the latest checkpoint for a run."""
    async for session in get_session():
        result = await session.execute(
            select(WorkflowCheckpointRecord)
            .where(WorkflowCheckpointRecord.run_id == run_id)
            .order_by(WorkflowCheckpointRecord.created_at.desc())
        )
        record = result.scalars().first()
        if record is None:
            return None
        return {
            "checkpoint_id": record.checkpoint_id,
            "run_id": record.run_id,
            "node_name": record.node_name,
            "node_path": record.node_path,
            "workflow_version": record.workflow_version,
            "logical_input_hash": record.logical_input_hash,
            "state": _as_dict(record.state_json),
            "status": record.status,
            "created_at": record.created_at,
        }
    raise RuntimeError("database session unavailable")


async def get_checkpoint(checkpoint_id: str) -> dict[str, Any] | None:
    """Fetch one checkpoint by id."""
    async for session in get_session():
        record = await session.get(WorkflowCheckpointRecord, checkpoint_id)
        if record is None:
            return None
        return {
            "checkpoint_id": record.checkpoint_id,
            "run_id": record.run_id,
            "node_name": record.node_name,
            "node_path": record.node_path,
            "workflow_version": record.workflow_version,
            "logical_input_hash": record.logical_input_hash,
            "state": _as_dict(record.state_json),
            "status": record.status,
            "created_at": record.created_at,
        }
    raise RuntimeError("database session unavailable")


async def record_node_execution(
    *,
    idempotency_key: str,
    run_id: str,
    node_name: str,
    node_path: str,
    workflow_version: str,
    logical_input_hash: str,
    result: dict[str, Any],
    checkpoint_id: str | None,
    status: str = "completed",
) -> dict[str, Any]:
    """Persist node execution metadata for replay skipping."""
    async for session in get_session():
        record = await session.get(WorkflowNodeExecutionRecord, idempotency_key)
        now = _utcnow()
        if record is None:
            record = WorkflowNodeExecutionRecord(
                idempotency_key=idempotency_key,
                run_id=run_id,
                node_name=node_name,
                node_path=node_path,
                workflow_version=workflow_version,
                logical_input_hash=logical_input_hash,
                status=status,
                result_json=_as_dict(result),
                checkpoint_id=checkpoint_id,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
        else:
            record.status = status
            record.result_json = _as_dict(result)
            record.checkpoint_id = checkpoint_id
            record.updated_at = now
        await session.commit()
        return {
            "idempotency_key": record.idempotency_key,
            "run_id": record.run_id,
            "node_name": record.node_name,
            "node_path": record.node_path,
            "workflow_version": record.workflow_version,
            "logical_input_hash": record.logical_input_hash,
            "status": record.status,
            "result": _as_dict(record.result_json),
            "checkpoint_id": record.checkpoint_id,
        }
    raise RuntimeError("database session unavailable")


async def get_node_execution(idempotency_key: str) -> dict[str, Any] | None:
    """Fetch persisted node execution metadata."""
    async for session in get_session():
        record = await session.get(WorkflowNodeExecutionRecord, idempotency_key)
        if record is None:
            return None
        return {
            "idempotency_key": record.idempotency_key,
            "run_id": record.run_id,
            "node_name": record.node_name,
            "node_path": record.node_path,
            "workflow_version": record.workflow_version,
            "logical_input_hash": record.logical_input_hash,
            "status": record.status,
            "result": _as_dict(record.result_json),
            "checkpoint_id": record.checkpoint_id,
        }
    raise RuntimeError("database session unavailable")


def _hash_event(event: dict[str, Any], previous_hash: str | None = None) -> str:
    payload = json.dumps(event, sort_keys=True, default=str)
    if previous_hash:
        payload = previous_hash + payload
    return hashlib.sha256(payload.encode()).hexdigest()


async def record_audit_event(
    *,
    run_id: str,
    event_type: str,
    principal: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one append-only audit record."""
    async for session in get_session():
        seq_result = await session.execute(
            select(func.max(AuditEventRecord.sequence)).where(AuditEventRecord.run_id == run_id)
        )
        max_sequence = seq_result.scalar_one_or_none()
        sequence = int(max_sequence or 0) + 1

        prev_result = await session.execute(
            select(AuditEventRecord)
            .where(AuditEventRecord.run_id == run_id)
            .order_by(AuditEventRecord.sequence.desc())
        )
        previous = prev_result.scalars().first()
        previous_hash = previous.chain_hash if previous is not None else None
        event = {
            "event_id": f"audit-{run_id}-{sequence:06d}",
            "run_id": run_id,
            "sequence": sequence,
            "event_type": event_type,
            "principal": principal or {},
            "details": details or {},
            "created_at": _utcnow(),
        }
        chain_hash = _hash_event(event, previous_hash)

        record = AuditEventRecord(
            event_id=str(event["event_id"]),
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            principal_json=_as_dict(principal),
            details_json=_as_dict(details),
            previous_hash=previous_hash,
            chain_hash=chain_hash,
            created_at=str(event["created_at"]),
        )
        session.add(record)
        await session.commit()
        event["previous_hash"] = previous_hash
        event["chain_hash"] = chain_hash
        return event
    raise RuntimeError("database session unavailable")


async def list_audit_events(run_id: str) -> list[dict[str, Any]]:
    """List audit events for a run."""
    async for session in get_session():
        result = await session.execute(
            select(AuditEventRecord)
            .where(AuditEventRecord.run_id == run_id)
            .order_by(AuditEventRecord.sequence)
        )
        records = result.scalars().all()
        return [
            {
                "event_id": record.event_id,
                "run_id": record.run_id,
                "sequence": record.sequence,
                "event_type": record.event_type,
                "principal": _as_dict(record.principal_json),
                "details": _as_dict(record.details_json),
                "previous_hash": record.previous_hash,
                "chain_hash": record.chain_hash,
                "created_at": record.created_at,
            }
            for record in records
        ]
    raise RuntimeError("database session unavailable")


async def verify_audit_chain(run_id: str) -> bool:
    """Verify the stored hash chain for one run."""
    events = await list_audit_events(run_id)
    for index, event in enumerate(events):
        previous_hash = events[index - 1]["chain_hash"] if index > 0 else None
        base = {
            "event_id": event["event_id"],
            "run_id": event["run_id"],
            "sequence": event["sequence"],
            "event_type": event["event_type"],
            "principal": event["principal"],
            "details": event["details"],
            "created_at": event["created_at"],
        }
        if _hash_event(base, previous_hash) != event["chain_hash"]:
            return False
    return True


async def save_approval_decision(
    *,
    run_id: str,
    approval_id: str,
    gate: str,
    required: bool,
    status: str,
    rationale: str,
    approver_id: str,
    display_data: dict[str, Any],
    decided_at: str | None,
) -> dict[str, Any]:
    """Persist current approval decision state."""
    record_id = f"{run_id}:{approval_id}"
    async for session in get_session():
        record = await session.get(ApprovalDecisionRecord, record_id)
        if record is None:
            record = ApprovalDecisionRecord(record_id=record_id, run_id=run_id, approval_id=approval_id, gate=gate)
            session.add(record)
        record.required = 1 if required else 0
        record.status = status
        record.rationale = rationale
        record.approver_id = approver_id
        record.display_data_json = _as_dict(display_data)
        record.decided_at = decided_at
        await session.commit()
        return {
            "approval_id": record.approval_id,
            "gate": record.gate,
            "required": bool(record.required),
            "status": record.status,
            "rationale": record.rationale,
            "approver_id": record.approver_id,
            "display_data": _as_dict(record.display_data_json),
            "decided_at": record.decided_at,
        }
    raise RuntimeError("database session unavailable")


async def list_approval_decisions(run_id: str) -> dict[str, dict[str, Any]]:
    """Fetch approval decisions keyed by approval id."""
    async for session in get_session():
        result = await session.execute(
            select(ApprovalDecisionRecord)
            .where(ApprovalDecisionRecord.run_id == run_id)
            .order_by(ApprovalDecisionRecord.approval_id)
        )
        records = result.scalars().all()
        return {
            record.approval_id: {
                "approval_id": record.approval_id,
                "gate": record.gate,
                "required": bool(record.required),
                "status": record.status,
                "rationale": record.rationale,
                "approver_id": record.approver_id,
                "display_data": _as_dict(record.display_data_json),
                "decided_at": record.decided_at,
            }
            for record in records
        }
    raise RuntimeError("database session unavailable")
