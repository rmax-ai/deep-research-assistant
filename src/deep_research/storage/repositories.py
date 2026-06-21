"""Repository helpers for persisted research runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from deep_research.storage.database import get_session
from deep_research.storage.models import ResearchRunRecord


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
        "error": record.error,
        "objective": _as_dict(record.objective_json),
        "scope": _as_dict(record.scope_json),
        "questions_count": record.questions_count,
        "claims_count": record.claims_count,
        "sources_count": record.sources_count,
    }


def _apply_run_data(record: ResearchRunRecord, run_data: dict[str, Any]) -> None:
    record.session_id = str(run_data.get("session_id", ""))
    record.status = str(run_data.get("status", "queued"))
    record.phase = str(run_data.get("phase", "planning"))
    record.created_at = str(run_data.get("created_at", ""))
    record.started_at = run_data.get("started_at")
    record.completed_at = run_data.get("completed_at")
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
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [_record_to_run_data(record) for record in records]
    raise RuntimeError("database session unavailable")


async def update_run(run_id: str, run_data: dict[str, Any]) -> dict[str, Any]:
    """Update a persisted run row."""
    payload = dict(run_data)
    payload["run_id"] = run_id
    return await create_run(payload)
