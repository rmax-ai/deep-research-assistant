"""Tests for the REST API endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from deep_research.api import routes
from deep_research.api.routes import app


async def _wait_for_run_completion(client: AsyncClient, run_id: str, timeout_seconds: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        response = await client.get(f"/v1/research-runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"completed", "failed"}:
            return data
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"Timed out waiting for run {run_id} to finish")
        await asyncio.sleep(0.01)


async def _cancel_background_tasks() -> None:
    tasks = list(routes._run_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    routes._run_tasks.clear()


@pytest.fixture(autouse=True)
async def stub_api_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import deep_research.settings as settings_module
    from deep_research.settings import get_settings
    from deep_research.storage.database import close_database, init_database
    from deep_research.telemetry.logging import configure_logging

    async def fake_web_search(query: str, max_results: int = 5, tool_context=None):
        return {
            "query": query,
            "total_results": 1,
            "results": [
                {
                    "title": f"Result for {query}",
                    "url": f"https://example.com/{abs(hash(query))}",
                    "snippet": f"Evidence for {query}",
                    "source_type": "primary",
                    "is_primary": True,
                }
            ],
        }

    db_path = tmp_path / "api-test.db"
    log_path = tmp_path / "api-test.log"
    monkeypatch.setenv("DEEP_RESEARCH_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("DEEP_RESEARCH_LOG_FILE_PATH", str(log_path))
    monkeypatch.setenv("DEEP_RESEARCH_EXA_API_KEY", "test-exa-key")
    monkeypatch.setattr(settings_module, "_settings", None)
    configure_logging(force=True)
    await close_database()
    await init_database()

    monkeypatch.setattr("deep_research.tools.search.web_search", fake_web_search)
    settings = get_settings()
    monkeypatch.setattr(settings.workflow, "enable_iterative_research", False)
    monkeypatch.setattr(settings.workflow, "enable_follow_up_questions", False)
    monkeypatch.setattr(settings.workflow, "maximum_parallel_questions", 1)
    monkeypatch.setattr(settings.approvals, "mode", "auto_approve")
    routes._active_runs.clear()
    await _cancel_background_tasks()
    routes.get_event_bus().reset()
    yield
    await _cancel_background_tasks()
    routes._active_runs.clear()
    routes.get_event_bus().reset()
    await close_database()
    monkeypatch.setattr(settings_module, "_settings", None)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestAPIHealth:
    async def test_startup_allows_health_checks_without_required_api_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        import deep_research.settings as settings_module

        monkeypatch.delenv("DEEP_RESEARCH_EXA_API_KEY", raising=False)
        monkeypatch.setattr(settings_module, "_settings", None)

        async with routes.lifespan(app):
            health = await routes.health()

        assert health["status"] == "ok"

        monkeypatch.setenv("DEEP_RESEARCH_EXA_API_KEY", "test-exa-key")
        monkeypatch.setattr(settings_module, "_settings", None)

    async def test_route_inventory_matches_supported_surface(self, client):
        del client
        expected = {
            ("GET", "/health"),
            ("POST", "/v1/research-runs"),
            ("GET", "/v1/research-runs/{run_id}"),
            ("GET", "/v1/research-runs/{run_id}/graph"),
            ("GET", "/v1/research-runs/{run_id}/frontier"),
            ("GET", "/v1/research-runs/{run_id}/progress"),
            ("GET", "/v1/research-runs/{run_id}/events"),
            ("GET", "/v1/research-runs/{run_id}/logs"),
            ("GET", "/v1/research-runs/{run_id}/concept-map"),
            ("POST", "/v1/research-runs/{run_id}/interventions"),
            ("POST", "/v1/research-runs/{run_id}/approvals/{approval_id}"),
            ("GET", "/v1/research-runs/{run_id}/approvals"),
            ("POST", "/v1/research-runs/{run_id}/exports"),
        }

        actual = set()
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            if path == "/health" or path.startswith("/v1/"):
                for method in methods - {"HEAD", "OPTIONS"}:
                    actual.add((method, path))

        assert actual == expected

    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_cors_preflight_for_create_run(self, client):
        response = await client.options(
            "/v1/research-runs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "POST" in response.headers["access-control-allow-methods"]

    async def test_cors_preflight_allows_other_localhost_ports(self, client):
        response = await client.options(
            "/v1/research-runs",
            headers={
                "Origin": "http://localhost:4321",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:4321"


@pytest.mark.asyncio
class TestCreateRun:
    async def test_create_run_returns_503_when_provider_configuration_is_missing(
        self, client, monkeypatch: pytest.MonkeyPatch
    ):
        import deep_research.settings as settings_module

        monkeypatch.delenv("DEEP_RESEARCH_EXA_API_KEY", raising=False)
        monkeypatch.setattr(settings_module, "_settings", None)

        response = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Unavailable provider",
                    "primary_question": "Why is run creation unavailable?",
                }
            },
        )

        assert response.status_code == 503
        assert "DEEP_RESEARCH_EXA_API_KEY" in response.json()["detail"]

        monkeypatch.setenv("DEEP_RESEARCH_EXA_API_KEY", "test-exa-key")
        monkeypatch.setattr(settings_module, "_settings", None)

    async def test_create_minimal(self, client):
        response = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Test Research",
                    "primary_question": "What is ADK 2.0?",
                }
            },
            timeout=60,
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "queued"
        completed = await _wait_for_run_completion(client, data["run_id"])
        assert completed["status"] == "completed"
        assert completed["report_preview"]

        progress = await client.get(f"/v1/research-runs/{data['run_id']}/progress")
        assert progress.status_code == 200
        assert progress.json()["phase"] == "completed"

    async def test_create_with_full_objective(self, client):
        response = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Security Analysis",
                    "primary_question": "Analyze security implications of AI agents",
                    "decision_to_support": "Define platform architecture",
                    "intended_audience": ["architects", "security"],
                    "output_type": "risk_memo",
                    "desired_depth": "deep",
                },
                "mode": "review_first",
            },
            timeout=60,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        completed = await _wait_for_run_completion(client, data["run_id"])
        assert completed["questions_count"] >= 0
        assert completed["claims_count"] >= 0

    async def test_invalid_objective(self, client):
        response = await client.post(
            "/v1/research-runs",
            json={"objective": {}},
        )
        assert response.status_code == 422

    async def test_strict_mode_pauses_for_required_approval(self, client, monkeypatch: pytest.MonkeyPatch):
        from deep_research.settings import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings.approvals, "mode", "strict")
        monkeypatch.setattr(settings.approvals, "scope_required_for_risk", "all")
        monkeypatch.setattr(settings.approvals, "plan_required_for_risk", "all")

        response = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Approval Test",
                    "primary_question": "Pause until a human approves",
                }
            },
            timeout=60,
        )
        assert response.status_code == 200
        run_id = response.json()["run_id"]

        deadline = asyncio.get_running_loop().time() + 5.0
        while True:
            status_response = await client.get(f"/v1/research-runs/{run_id}")
            data = status_response.json()
            if data["status"] == "awaiting_approval":
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Timed out waiting for awaiting_approval")
            await asyncio.sleep(0.01)

        assert data["awaiting_approval_gate"] == "A"

        approvals = await client.get(f"/v1/research-runs/{run_id}/approvals")
        assert approvals.status_code == 200
        assert approvals.json()["approvals"]["A"]["status"] == "pending"

        approve = await client.post(
            f"/v1/research-runs/{run_id}/approvals/A",
            json={"decision": "approved", "rationale": "Proceed"},
            timeout=60,
        )
        assert approve.status_code == 200
        next_status = await client.get(f"/v1/research-runs/{run_id}")
        assert next_status.json()["status"] in {"queued", "running", "awaiting_approval", "completed"}


@pytest.mark.asyncio
class TestGetRun:
    async def test_get_existing_run(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Get Test",
                    "primary_question": "What is testing?",
                }
            },
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.get(f"/v1/research-runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id

    async def test_get_nonexistent_run(self, client):
        response = await client.get("/v1/research-runs/nonexistent")
        assert response.status_code == 404

    async def test_get_persisted_run_after_in_memory_cache_is_cleared(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Persisted Test", "primary_question": "Does SQLite survive restart?"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        routes._active_runs.clear()

        response = await client.get(f"/v1/research-runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    async def test_queued_run_is_persisted_before_background_completion(self, client):
        response = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Queued Persistence", "primary_question": "Persist queued row"}},
            timeout=60,
        )
        run_id = response.json()["run_id"]

        routes._active_runs.clear()

        queued = await client.get(f"/v1/research-runs/{run_id}")
        assert queued.status_code == 200
        assert queued.json()["status"] in {"queued", "running", "completed"}

    async def test_failed_run_is_persisted_with_error(self, client, monkeypatch: pytest.MonkeyPatch):
        def broken_run_async(self, *args, **kwargs):
            del self, args, kwargs

            async def _iter():
                raise RuntimeError("forced workflow failure")
                yield None

            return _iter()

        monkeypatch.setattr(routes.InMemoryRunner, "run_async", broken_run_async)

        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Failure Test", "primary_question": "Break the runner"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        failed = await _wait_for_run_completion(client, run_id)
        assert failed["status"] == "failed"

        routes._active_runs.clear()
        persisted = await routes.get_run(run_id)
        assert persisted is not None
        assert persisted["status"] == "failed"
        assert persisted["error"] == "forced workflow failure"

    async def test_startup_requeues_persisted_queued_run(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Resume Queued", "primary_question": "Resume me after restart"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

        await _cancel_background_tasks()
        routes._active_runs.clear()

        persisted = await routes.get_run(run_id)
        assert persisted is not None
        assert persisted["status"] in {"queued", "running"}

        await routes._resume_incomplete_runs()
        assert run_id in routes._run_tasks

        completed = await _wait_for_run_completion(client, run_id)
        assert completed["status"] == "completed"

    async def test_startup_requeues_persisted_running_run(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Resume Running", "primary_question": "Treat running as resumable"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

        await _cancel_background_tasks()
        routes._active_runs.clear()
        persisted = await routes.get_run(run_id)
        assert persisted is not None

        await routes.update_run(
            run_id,
            {
                **persisted,
                "status": "running",
                "phase": "researching",
            },
        )

        await routes._resume_incomplete_runs()
        assert run_id in routes._run_tasks

        completed = await _wait_for_run_completion(client, run_id)
        assert completed["status"] == "completed"


@pytest.mark.asyncio
class TestCollaborationEndpoints:
    async def test_frontier_endpoint_returns_structured_data(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Frontier Test", "primary_question": "Map tool governance"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.get(f"/v1/research-runs/{run_id}/frontier")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "questions" in data
        assert "priorities" in data

    async def test_progress_endpoint_returns_budget_and_phase(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Progress Test", "primary_question": "Map approval gates"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

        response = await client.get(f"/v1/research-runs/{run_id}/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "phase" in data
        assert "budget" in data

    async def test_events_sse_endpoint_replays_events(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Events Test", "primary_question": "Trace event emission"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        async with client.stream("GET", f"/v1/research-runs/{run_id}/events") as response:
            body = await response.aread()

        assert response.status_code == 200
        text = body.decode()
        assert "event: run.started" in text
        assert "event: node.started" in text
        assert "event: report.generated" in text
        assert "event: run.completed" in text

    async def test_logs_endpoint_returns_file_backed_records_for_run(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Logs Test", "primary_question": "Capture run logs"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.get(f"/v1/research-runs/{run_id}/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["count"] > 0
        assert all(record["run_id"] == run_id for record in data["records"])

    async def test_running_run_accumulates_live_progress_events(self, client, monkeypatch: pytest.MonkeyPatch):
        from deep_research.agents.research_director import (
            research_director as original_research_director,
        )

        async def slow_research_director(*args, **kwargs):
            await asyncio.sleep(0.05)
            return await original_research_director(*args, **kwargs)

        monkeypatch.setattr("deep_research.agents.research_director.research_director", slow_research_director)

        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Live Events", "primary_question": "Show node progress"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

        deadline = asyncio.get_running_loop().time() + 2.0
        while True:
            run_data = routes._active_runs.get(run_id)
            if run_data and run_data.get("events"):
                event_types = [event["event_type"] for event in run_data["events"]]
                assert "node.started" in event_types
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Timed out waiting for live progress events")
            await asyncio.sleep(0.01)

        await _wait_for_run_completion(client, run_id)

    async def test_concept_map_endpoint_returns_topic_graph(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Concept Map Test", "primary_question": "Organize claims by topic"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.get(f"/v1/research-runs/{run_id}/concept-map")
        assert response.status_code == 200
        data = response.json()
        assert "topic_nodes" in data
        assert "edges" in data

    async def test_intervention_endpoint_records_add_question(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Intervention Test", "primary_question": "Baseline run"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.post(
            f"/v1/research-runs/{run_id}/interventions",
            json={"type": "add_question", "instruction": "Investigate audit log retention."},
        )
        assert response.status_code == 200

        frontier = await client.get(f"/v1/research-runs/{run_id}/frontier")
        questions = frontier.json()["questions"]
        assert any(question["text"] == "Investigate audit log retention." for question in questions)

        routes._active_runs.clear()
        frontier_after_restart = await client.get(f"/v1/research-runs/{run_id}/frontier")
        persisted_questions = frontier_after_restart.json()["questions"]
        assert any(question["text"] == "Investigate audit log retention." for question in persisted_questions)

    async def test_approval_endpoint_records_decision(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Approval Test", "primary_question": "Need gate updates"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.post(
            f"/v1/research-runs/{run_id}/approvals/C",
            json={"decision": "rejected", "rationale": "Need more evidence."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["approval_id"] == "C"
        assert data["status"] == "rejected"

    async def test_get_approvals_endpoint_returns_gate_state(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Approval Readback", "primary_question": "Need gate state"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        await client.post(
            f"/v1/research-runs/{run_id}/approvals/C",
            json={"decision": "approved", "rationale": "Looks good."},
        )

        response = await client.get(f"/v1/research-runs/{run_id}/approvals")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["approvals"]["C"]["status"] == "approved"

        routes._active_runs.clear()
        persisted = await client.get(f"/v1/research-runs/{run_id}/approvals")
        assert persisted.json()["approvals"]["C"]["status"] == "approved"


@pytest.mark.asyncio
class TestExport:
    async def test_export_report(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={
                "objective": {
                    "title": "Export Test",
                    "primary_question": "Export test question",
                }
            },
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]
        await _wait_for_run_completion(client, run_id)

        response = await client.post(f"/v1/research-runs/{run_id}/exports?format=markdown")
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["format"] == "markdown"
        assert data["content_length"] > 0
        assert "Report generation in progress" not in data["content"]
        assert "## Referenced Sources" in data["content"]
        assert "https://example.com/" in data["content"]
