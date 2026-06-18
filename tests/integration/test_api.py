"""Tests for the REST API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from deep_research.api.routes import app


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
            json={"objective": {}},  # missing required fields
        )
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestGetRun:
    async def test_get_existing_run(self, client):
        # Create first
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

        # Then get
        response = await client.get(f"/v1/research-runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id

    async def test_get_nonexistent_run(self, client):
        response = await client.get("/v1/research-runs/nonexistent")
        assert response.status_code == 404


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
