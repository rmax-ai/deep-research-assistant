"""Tests for the REST API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from deep_research.api.routes import app


@pytest.fixture(autouse=True)
def stub_api_dependencies(monkeypatch: pytest.MonkeyPatch):
    from deep_research.settings import get_settings

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

    monkeypatch.setattr("deep_research.tools.search.web_search", fake_web_search)
    settings = get_settings()
    monkeypatch.setattr(settings.workflow, "enable_iterative_research", False)
    monkeypatch.setattr(settings.workflow, "enable_follow_up_questions", False)
    monkeypatch.setattr(settings.workflow, "maximum_parallel_questions", 1)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestAPIHealth:
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
class TestCreateRun:
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
        assert data["status"] == "completed"

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
        assert data["questions_count"] >= 0
        assert data["claims_count"] >= 0

    async def test_invalid_objective(self, client):
        response = await client.post(
            "/v1/research-runs",
            json={"objective": {}},
        )
        assert response.status_code == 422


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

        response = await client.get(f"/v1/research-runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id

    async def test_get_nonexistent_run(self, client):
        response = await client.get("/v1/research-runs/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCollaborationEndpoints:
    async def test_frontier_endpoint_returns_structured_data(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Frontier Test", "primary_question": "Map tool governance"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

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

        async with client.stream("GET", f"/v1/research-runs/{run_id}/events") as response:
            body = await response.aread()

        assert response.status_code == 200
        text = body.decode()
        assert "event: run.started" in text
        assert "event: run.completed" in text

    async def test_concept_map_endpoint_returns_topic_graph(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Concept Map Test", "primary_question": "Organize claims by topic"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

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

        response = await client.post(
            f"/v1/research-runs/{run_id}/interventions",
            json={"type": "add_question", "instruction": "Investigate audit log retention."},
        )
        assert response.status_code == 200

        frontier = await client.get(f"/v1/research-runs/{run_id}/frontier")
        questions = frontier.json()["questions"]
        assert any(question["text"] == "Investigate audit log retention." for question in questions)

    async def test_approval_endpoint_records_decision(self, client):
        create_resp = await client.post(
            "/v1/research-runs",
            json={"objective": {"title": "Approval Test", "primary_question": "Need gate updates"}},
            timeout=60,
        )
        run_id = create_resp.json()["run_id"]

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

        await client.post(
            f"/v1/research-runs/{run_id}/approvals/C",
            json={"decision": "approved", "rationale": "Looks good."},
        )

        response = await client.get(f"/v1/research-runs/{run_id}/approvals")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["approvals"]["C"]["status"] == "approved"


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

        response = await client.post(f"/v1/research-runs/{run_id}/exports?format=markdown")
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["format"] == "markdown"
