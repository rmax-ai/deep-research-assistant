from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
async def sqlite_run_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import deep_research.settings as settings_module
    from deep_research.storage.database import close_database, init_database

    db_path = tmp_path / "runs.db"
    monkeypatch.setenv("DEEP_RESEARCH_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(settings_module, "_settings", None)
    await close_database()
    await init_database()
    yield
    await close_database()
    monkeypatch.setattr(settings_module, "_settings", None)


@pytest.mark.asyncio
async def test_persisted_run_round_trips_full_state(sqlite_run_store):
    from deep_research.storage.repositories import create_run, get_run, update_run

    run_data = {
        "run_id": "run-1",
        "session_id": "session-run-1",
        "status": "queued",
        "phase": "planning",
        "report": "",
        "event_count": 0,
        "events": [],
        "state": {"app:run_id": "run-1", "app:questions": [{"text": "Q1"}]},
        "approvals": {"A": {"status": "approved"}},
        "interventions": [{"type": "add_question", "instruction": "Inspect persistence"}],
        "created_at": "2026-06-21T00:00:00+00:00",
        "objective": {"title": "Test"},
        "scope": {"risk_level": "low"},
        "questions_count": 1,
        "claims_count": 0,
        "sources_count": 0,
    }

    created = await create_run(run_data)
    assert created["run_id"] == "run-1"
    assert created["state"]["app:questions"][0]["text"] == "Q1"

    await update_run(
        "run-1",
        {
            **created,
            "status": "completed",
            "phase": "completed",
            "report": "final report",
            "completed_at": "2026-06-21T00:01:00+00:00",
            "claims_count": 2,
        },
    )

    loaded = await get_run("run-1")
    assert loaded is not None
    assert loaded["status"] == "completed"
    assert loaded["report"] == "final report"
    assert loaded["approvals"]["A"]["status"] == "approved"
    assert loaded["interventions"][0]["instruction"] == "Inspect persistence"
    assert loaded["claims_count"] == 2


@pytest.mark.asyncio
async def test_get_run_returns_none_for_unknown_id(sqlite_run_store):
    from deep_research.storage.repositories import get_run

    assert await get_run("missing") is None


@pytest.mark.asyncio
async def test_list_runs_filters_by_status(sqlite_run_store):
    from deep_research.storage.repositories import create_run, list_runs

    await create_run(
        {
            "run_id": "run-queued",
            "session_id": "session-run-queued",
            "status": "queued",
            "phase": "planning",
            "report": "",
            "event_count": 0,
            "events": [],
            "state": {"app:run_id": "run-queued"},
            "approvals": {},
            "interventions": [],
            "created_at": "2026-06-21T00:00:00+00:00",
            "objective": {"title": "Queued"},
            "scope": {},
            "questions_count": 0,
            "claims_count": 0,
            "sources_count": 0,
        }
    )
    await create_run(
        {
            "run_id": "run-completed",
            "session_id": "session-run-completed",
            "status": "completed",
            "phase": "completed",
            "report": "done",
            "event_count": 0,
            "events": [],
            "state": {"app:run_id": "run-completed"},
            "approvals": {},
            "interventions": [],
            "created_at": "2026-06-21T00:00:00+00:00",
            "objective": {"title": "Done"},
            "scope": {},
            "questions_count": 0,
            "claims_count": 0,
            "sources_count": 0,
        }
    )

    queued = await list_runs(statuses=["queued"])
    assert [run["run_id"] for run in queued] == ["run-queued"]


@pytest.mark.asyncio
async def test_checkpoint_and_node_execution_round_trip(sqlite_run_store):
    from deep_research.storage.repositories import (
        create_run,
        create_workflow_checkpoint,
        get_latest_checkpoint,
        get_node_execution,
        record_node_execution,
    )

    await create_run(
        {
            "run_id": "run-checkpoint",
            "session_id": "session-run-checkpoint",
            "status": "running",
            "phase": "researching",
            "report": "",
            "event_count": 0,
            "events": [],
            "state": {"app:run_id": "run-checkpoint", "app:phase": "researching"},
            "approvals": {},
            "interventions": [],
            "created_at": "2026-06-21T00:00:00+00:00",
            "objective": {"title": "Checkpoint"},
            "scope": {},
            "questions_count": 0,
            "claims_count": 0,
            "sources_count": 0,
        }
    )
    checkpoint = await create_workflow_checkpoint(
        run_id="run-checkpoint",
        node_name="question_graph_build",
        node_path="question_graph_build",
        workflow_version="1.0.0",
        logical_input_hash="hash-1",
        state={"app:run_id": "run-checkpoint", "app:questions": [{"text": "Q1"}]},
    )
    assert checkpoint["node_name"] == "question_graph_build"

    await record_node_execution(
        idempotency_key="idem-1",
        run_id="run-checkpoint",
        node_name="question_graph_build",
        node_path="question_graph_build",
        workflow_version="1.0.0",
        logical_input_hash="hash-1",
        result={"question_count": 1},
        checkpoint_id=checkpoint["checkpoint_id"],
    )

    latest = await get_latest_checkpoint("run-checkpoint")
    execution = await get_node_execution("idem-1")
    assert latest is not None
    assert latest["checkpoint_id"] == checkpoint["checkpoint_id"]
    assert execution is not None
    assert execution["result"]["question_count"] == 1


@pytest.mark.asyncio
async def test_audit_chain_and_approval_decisions_are_persisted(sqlite_run_store):
    from deep_research.storage.repositories import (
        create_run,
        list_approval_decisions,
        record_audit_event,
        save_approval_decision,
        verify_audit_chain,
    )

    await create_run(
        {
            "run_id": "run-audit",
            "session_id": "session-run-audit",
            "status": "queued",
            "phase": "planning",
            "report": "",
            "event_count": 0,
            "events": [],
            "state": {"app:run_id": "run-audit"},
            "approvals": {},
            "interventions": [],
            "created_at": "2026-06-21T00:00:00+00:00",
            "objective": {"title": "Audit"},
            "scope": {},
            "questions_count": 0,
            "claims_count": 0,
            "sources_count": 0,
        }
    )
    await record_audit_event(run_id="run-audit", event_type="run.started", principal={"user_id": "alice"})
    await record_audit_event(run_id="run-audit", event_type="approval.requested", principal={"user_id": "alice"})
    await save_approval_decision(
        run_id="run-audit",
        approval_id="A",
        gate="A",
        required=True,
        status="approved",
        rationale="ok",
        approver_id="alice",
        display_data={"risk_level": "high"},
        decided_at="2026-06-21T00:00:05+00:00",
    )

    approvals = await list_approval_decisions("run-audit")
    assert approvals["A"]["status"] == "approved"
    assert await verify_audit_chain("run-audit") is True
