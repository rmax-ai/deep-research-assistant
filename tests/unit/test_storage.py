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
