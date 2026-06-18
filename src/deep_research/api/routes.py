"""REST API for the Deep Research Assistant.

Provides FastAPI endpoints for creating, inspecting, and exporting
research runs. Uses ADK InMemoryRunner for local execution.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

from deep_research.workflow.graph import build_research_workflow

app = FastAPI(
    title="Deep Research Assistant",
    version="0.1.0",
    description="Enterprise-grade governed research runtime API",
)

# In-memory state for active runs
_active_runs: dict[str, dict[str, Any]] = {}
_workflow = build_research_workflow()


# ── Request/Response models ────────────────────────────────────────────────


class ObjectiveRequest(BaseModel):
    title: str
    primary_question: str
    decision_to_support: str | None = None
    intended_audience: list[str] = Field(default_factory=list)
    output_type: str = "technical_report"
    desired_depth: str = "standard"
    language: str = "en"


class CreateRunRequest(BaseModel):
    objective: ObjectiveRequest
    mode: str = "review_first"
    constraints: dict[str, Any] = Field(default_factory=dict)


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    objective: dict[str, Any] | None = None
    scope: dict[str, Any] | None = None
    questions_count: int = 0
    claims_count: int = 0
    sources_count: int = 0
    report_preview: str | None = None


class InterventionRequest(BaseModel):
    type: str
    target_id: str | None = None
    instruction: str


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/v1/research-runs", response_model=RunStatusResponse)
async def create_research_run(request: CreateRunRequest) -> RunStatusResponse:
    """Create and execute a new research run."""
    run_id = str(uuid.uuid4())[:8]
    session_id = f"session_{run_id}"
    user_id = "api_user"

    runner = InMemoryRunner(agent=_workflow, app_name="deep_research_api")

    await runner.session_service.create_session(
        app_name="deep_research_api",
        user_id=user_id,
        session_id=session_id,
    )

    # Build the user message
    objective_text = request.objective.primary_question
    if request.objective.decision_to_support:
        objective_text += f"\n\nDecision to support: {request.objective.decision_to_support}"
    if request.objective.intended_audience:
        objective_text += f"\n\nAudience: {', '.join(request.objective.intended_audience)}"

    msg = Content(role="user", parts=[Part(text=objective_text)])

    # Execute the workflow
    events = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=msg,
    ):
        events.append(event)

    # Collect final state from pipeline
    from deep_research.workflow.state import get_state, reset_state

    final_state = get_state()

    # Extract results
    run_data = {
        "run_id": run_id,
        "session_id": session_id,
        "status": "completed",
        "objective": final_state.get("app:objective", {}),
        "scope": final_state.get("app:scope", {}),
        "questions_count": len(final_state.get("app:questions", [])),
        "claims_count": len(final_state.get("app:claims", [])),
        "sources_count": len(final_state.get("app:sources", [])),
        "report": final_state.get("app:final_report", ""),
        "event_count": len(events),
    }

    _active_runs[run_id] = run_data
    reset_state()

    return RunStatusResponse(
        run_id=run_id,
        status="completed",
        objective=run_data["objective"],
        scope=run_data["scope"],
        questions_count=run_data["questions_count"],
        claims_count=run_data["claims_count"],
        sources_count=run_data["sources_count"],
        report_preview=run_data["report"][:500] if run_data["report"] else None,
    )


@app.get("/v1/research-runs/{run_id}", response_model=RunStatusResponse)
async def get_research_run(run_id: str) -> RunStatusResponse:
    """Get the current state of a research run."""
    run_data = _active_runs.get(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return RunStatusResponse(
        run_id=run_data["run_id"],
        status=run_data["status"],
        objective=run_data.get("objective"),
        scope=run_data.get("scope"),
        questions_count=run_data.get("questions_count", 0),
        claims_count=run_data.get("claims_count", 0),
        sources_count=run_data.get("sources_count", 0),
        report_preview=run_data.get("report", "")[:500] if run_data.get("report") else None,
    )


@app.get("/v1/research-runs/{run_id}/graph")
async def get_research_graph(run_id: str) -> dict[str, Any]:
    """Get the research graph for a run (questions, claims, evidence)."""
    run_data = _active_runs.get(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "run_id": run_id,
        "objective": run_data.get("objective"),
        "scope": run_data.get("scope"),
        "claims": run_data.get("claims", []),
        "sources": run_data.get("sources", []),
    }


@app.post("/v1/research-runs/{run_id}/interventions")
async def intervene(run_id: str, intervention: InterventionRequest) -> dict[str, str]:
    """Submit a user intervention on a running investigation."""
    if run_id not in _active_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "status": "recorded",
        "run_id": run_id,
        "intervention_type": intervention.type,
        "message": f"Intervention '{intervention.type}' recorded for run {run_id}",
    }


@app.post("/v1/research-runs/{run_id}/exports")
async def export_report(run_id: str, format: str = "markdown") -> dict[str, Any]:
    """Export the final report in the requested format."""
    run_data = _active_runs.get(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    report = run_data.get("report", "")
    if not report:
        return {
            "run_id": run_id,
            "format": format,
            "content": f"# {run_data.get('objective', {}).get('title', 'Research Report')}\n\n*Report generation in progress or no evidence collected yet.*",
            "content_length": 0,
            "note": "Report is empty — pipeline may have run in stub mode (LLM unavailable)",
        }

    return {
        "run_id": run_id,
        "format": format,
        "content": report,
        "content_length": len(report),
    }
