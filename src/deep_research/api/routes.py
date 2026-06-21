"""REST API for the Deep Research Assistant."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.agents.base_agent import BaseAgent
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

from deep_research.nodes.scope import apply_scope_change
from deep_research.storage.database import close_database, init_database
from deep_research.storage.repositories import create_run, get_run, list_runs, update_run
from deep_research.telemetry import configure_logging
from deep_research.telemetry.events import get_event_bus
from deep_research.workflow.graph import build_research_workflow
from deep_research.workflow.state import get_state, reset_state, set_state

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize and dispose app-scoped resources."""
    await init_database()
    await _resume_incomplete_runs()
    yield
    await _cancel_background_tasks()
    await close_database()


app = FastAPI(
    title="Deep Research Assistant",
    version="0.1.0",
    description="Enterprise-grade governed research runtime API",
    lifespan=lifespan,
)

_active_runs: dict[str, dict[str, Any]] = {}
_run_tasks: dict[str, asyncio.Task[None]] = {}
_workflow = build_research_workflow()


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


class FrontierResponse(BaseModel):
    run_id: str
    version: int = 0
    questions: list[dict[str, Any]] = Field(default_factory=list)
    priorities: dict[str, float] = Field(default_factory=dict)


class ProgressResponse(BaseModel):
    run_id: str
    phase: str
    budget: dict[str, Any] = Field(default_factory=dict)
    estimates: dict[str, Any] = Field(default_factory=dict)


class InterventionRequest(BaseModel):
    type: str
    target_id: str | None = None
    instruction: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalActionRequest(BaseModel):
    decision: str
    rationale: str = ""
    approver_id: str = "api_user"


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _load_run(run_id: str) -> dict[str, Any] | None:
    run_data = _active_runs.get(run_id)
    if run_data is not None:
        return run_data
    return await get_run(run_id)


async def _require_run(run_id: str) -> dict[str, Any]:
    run_data = await _load_run(run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run_data


def _sync_run_summary(run_data: dict[str, Any]) -> None:
    state = run_data.get("state", {})
    state_objective = state.get("app:objective", {})
    state_scope = state.get("app:scope", {})
    run_data["objective"] = state_objective if state_objective else run_data.get("objective", {})
    run_data["scope"] = state_scope if state_scope else run_data.get("scope", {})
    run_data["questions_count"] = len(state.get("app:questions", []))
    run_data["claims_count"] = len(state.get("app:claims", []))
    run_data["sources_count"] = len(state.get("app:sources", []))
    run_data["report"] = state.get("app:final_report", run_data.get("report", ""))
    run_data["phase"] = state.get("app:phase", run_data.get("phase", "completed"))


async def _persist_run(run_data: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    _sync_run_summary(run_data)
    persisted = await (create_run(run_data) if create else update_run(str(run_data["run_id"]), run_data))
    run_data.update(persisted)
    return run_data


def _default_approval_inputs(mode: str) -> dict[str, dict[str, str]]:
    return {
        "A": {"status": "approved"},
        "B": {"status": "approved"},
        "C": {"status": "approved"},
        "D": {"status": "approved"},
    }


def _build_objective_text(request: ObjectiveRequest) -> str:
    objective_text = request.primary_question
    if request.decision_to_support:
        objective_text += f"\n\nDecision to support: {request.decision_to_support}"
    if request.intended_audience:
        objective_text += f"\n\nAudience: {', '.join(request.intended_audience)}"
    return objective_text


def _objective_text_from_run_data(run_data: dict[str, Any]) -> str:
    state = run_data.get("state", {})
    if isinstance(state, dict):
        text = state.get("app:initial_objective_text")
        if isinstance(text, str) and text.strip():
            return text

    objective = run_data.get("objective", {})
    if isinstance(objective, dict):
        primary_question = objective.get("primary_question")
        if isinstance(primary_question, str) and primary_question.strip():
            text = primary_question
            decision = objective.get("decision_to_support")
            if isinstance(decision, str) and decision.strip():
                text += f"\n\nDecision to support: {decision}"
            audience = objective.get("intended_audience")
            if isinstance(audience, list) and audience:
                audience_values = [str(item) for item in audience if str(item).strip()]
                if audience_values:
                    text += f"\n\nAudience: {', '.join(audience_values)}"
            return text
    return ""


async def _cancel_background_tasks() -> None:
    tasks = list(_run_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _run_tasks.clear()


def _schedule_run_execution(run_data: dict[str, Any], *, resumed: bool = False) -> None:
    run_id = str(run_data["run_id"])
    if run_id in _run_tasks:
        return

    state = run_data.setdefault("state", {})
    session_id = str(run_data.get("session_id", f"session_{run_id}"))
    objective_text = _objective_text_from_run_data(run_data)
    if not objective_text:
        logger.warning("skipping run resume without objective text", extra={"run_id": run_id})
        return

    if resumed:
        run_data["status"] = "queued"
        run_data["phase"] = str(state.get("app:phase", run_data.get("phase", "planning")))
        run_data["completed_at"] = None
        run_data["error"] = None
        state["app:resumed_after_restart"] = True

    _active_runs[run_id] = run_data
    _run_tasks[run_id] = asyncio.create_task(
        _execute_research_run(
            run_id=run_id,
            session_id=session_id,
            user_id="api_user",
            objective_text=objective_text,
            state=state,
        )
    )


async def _resume_incomplete_runs() -> None:
    persisted_runs = await list_runs(statuses=["queued", "running"])
    for run_data in persisted_runs:
        run_id = str(run_data["run_id"])
        logger.info(
            "requeueing persisted run on startup",
            extra={"run_id": run_id, "status": run_data.get("status", "queued")},
        )
        _schedule_run_execution(run_data, resumed=True)


async def _execute_research_run(
    *,
    run_id: str,
    session_id: str,
    user_id: str,
    objective_text: str,
    state: dict[str, Any],
) -> None:
    run_data = await _require_run(run_id)
    run_data["status"] = "running"
    run_data["started_at"] = _now()
    await _persist_run(run_data)
    set_state(state)
    bus = get_event_bus()
    live_events = run_data.setdefault("events", [])

    async def _append_live_event(event: dict[str, Any]) -> None:
        if event.get("run_id") == run_id:
            live_events.append(event)

    unsubscribe = bus.subscribe("*", _append_live_event)
    logger.info("research run started", extra={"run_id": run_id, "status": "running"})

    runner = InMemoryRunner(agent=cast(BaseAgent, _workflow), app_name="deep_research_api")
    await runner.session_service.create_session(
        app_name="deep_research_api",
        user_id=user_id,
        session_id=session_id,
    )

    msg = Content(role="user", parts=[Part(text=objective_text)])

    try:
        events = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=msg,
        ):
            events.append(event)
            run_data["event_count"] = len(events)

        final_state = deepcopy(get_state())
        terminal_run_data = dict(run_data)
        terminal_run_data["state"] = final_state
        terminal_run_data["status"] = "completed"
        terminal_run_data["phase"] = final_state.get("app:phase", "completed")
        terminal_run_data["report"] = final_state.get("app:final_report", "")
        terminal_run_data["approvals"] = deepcopy(final_state.get("app:approval_decisions", {}))
        terminal_run_data["interventions"] = list(final_state.get("app:pending_interventions", []))
        terminal_run_data["completed_at"] = _now()
        logger.info(
            "research run completed",
            extra={
                "run_id": run_id,
                "status": "completed",
                "phase": terminal_run_data["phase"],
                "event_count": len(live_events),
            },
        )
        await _persist_run(terminal_run_data)
        run_data.clear()
        run_data.update(terminal_run_data)
    except Exception as exc:
        final_state = deepcopy(get_state())
        terminal_run_data = dict(run_data)
        terminal_run_data["state"] = final_state
        terminal_run_data["status"] = "failed"
        terminal_run_data["phase"] = final_state.get("app:phase", run_data.get("phase", "failed"))
        terminal_run_data["error"] = str(exc)
        terminal_run_data["completed_at"] = _now()
        logger.exception(
            "research run failed",
            extra={
                "run_id": run_id,
                "status": "failed",
                "phase": terminal_run_data["phase"],
                "error_type": type(exc).__name__,
            },
        )
        await _persist_run(terminal_run_data)
        run_data.clear()
        run_data.update(terminal_run_data)
    finally:
        unsubscribe()
        reset_state()
        _run_tasks.pop(run_id, None)
        _active_runs.pop(run_id, None)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/v1/research-runs", response_model=RunStatusResponse)
async def create_research_run(request: CreateRunRequest) -> RunStatusResponse:
    """Create a new research run and execute it asynchronously."""
    run_id = str(uuid.uuid4())[:8]
    session_id = f"session_{run_id}"
    state: dict[str, Any] = {}
    state["app:run_id"] = run_id
    state["app:run_mode"] = request.mode
    state["app:phase"] = "planning"
    state["app:approval_inputs"] = deepcopy(
        request.constraints.get("approval_inputs", _default_approval_inputs(request.mode))
    )
    state["app:pending_interventions"] = list(request.constraints.get("interventions", []))
    state["app:initial_objective_text"] = _build_objective_text(request.objective)
    run_data = {
        "run_id": run_id,
        "session_id": session_id,
        "status": "queued",
        "phase": state.get("app:phase", "planning"),
        "report": "",
        "event_count": 0,
        "events": [],
        "state": state,
        "approvals": {},
        "interventions": list(state.get("app:pending_interventions", [])),
        "created_at": _now(),
        "objective": request.objective.model_dump(),
        "scope": {},
    }
    await _persist_run(run_data, create=True)
    _schedule_run_execution(run_data)

    return RunStatusResponse(
        run_id=run_id,
        status=run_data["status"],
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
    run_data = await _require_run(run_id)
    _sync_run_summary(run_data)
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
    """Get the research graph for a run."""
    run_data = await _require_run(run_id)
    state = run_data.get("state", {})
    return {
        "run_id": run_id,
        "objective": run_data.get("objective"),
        "scope": run_data.get("scope"),
        "claims": state.get("app:claims", []),
        "sources": state.get("app:sources", []),
    }


@app.get("/v1/research-runs/{run_id}/frontier", response_model=FrontierResponse)
async def get_research_frontier(run_id: str) -> FrontierResponse:
    """Return the live research frontier."""
    run_data = await _require_run(run_id)
    state = run_data.get("state", {})
    return FrontierResponse(
        run_id=run_id,
        version=int(state.get("app:questions_version", 0)),
        questions=state.get("app:questions", []),
        priorities=state.get("app:question_priorities", {}),
    )


@app.get("/v1/research-runs/{run_id}/progress", response_model=ProgressResponse)
async def get_research_progress(run_id: str) -> ProgressResponse:
    """Return phase and budget progress."""
    run_data = await _require_run(run_id)
    state = run_data.get("state", {})
    budget = {
        "perspectives": state.get("app:perspective_budgets", {}),
        "last_check": state.get("app:last_budget_check", {}),
    }
    estimates = {
        "cycles_completed": len(state.get("app:cycle_history", [])),
        "claims": len(state.get("app:claims", [])),
        "sources": len(state.get("app:sources", [])),
    }
    return ProgressResponse(
        run_id=run_id,
        phase=state.get("app:phase", run_data.get("phase", "completed")),
        budget=budget,
        estimates=estimates,
    )


@app.get("/v1/research-runs/{run_id}/events")
async def get_research_events(run_id: str, since: str | None = None) -> StreamingResponse:
    """Stream or replay run events as server-sent events."""
    run_data = await _require_run(run_id)
    bus = get_event_bus()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    backlog = bus.get_events_since(run_id, since)
    terminal_events = {"run.completed", "run.failed"}

    async def _enqueue(event: dict[str, Any]) -> None:
        if event.get("run_id") == run_id:
            await queue.put(event)
            if event.get("event_type") in terminal_events:
                await queue.put(None)

    unsubscribe = bus.subscribe("*", _enqueue)
    for event in backlog:
        await queue.put(event)
    if run_data.get("status") in {"completed", "failed"} and (
        not backlog or backlog[-1].get("event_type") not in terminal_events
    ):
        await queue.put(None)

    async def event_stream() -> AsyncIterator[str]:
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"event: {item['event_type']}\ndata: {json.dumps(item)}\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/v1/research-runs/{run_id}/concept-map")
async def get_concept_map(run_id: str) -> dict[str, Any]:
    """Return the projected topic graph."""
    run_data = await _require_run(run_id)
    concept_map = run_data.get("state", {}).get("app:concept_map")
    if isinstance(concept_map, dict):
        return concept_map
    return {"topic_nodes": [], "edges": [], "version": 0}


@app.post("/v1/research-runs/{run_id}/interventions")
async def intervene(run_id: str, intervention: InterventionRequest) -> dict[str, Any]:
    """Submit a user intervention on a run."""
    run_data = await _require_run(run_id)
    state = run_data.setdefault("state", {})
    record = {
        "type": intervention.type,
        "target_id": intervention.target_id,
        "instruction": intervention.instruction,
        **intervention.metadata,
    }
    run_data.setdefault("interventions", []).append(record)

    if intervention.type in {"add_topic", "remove_topic", "add_perspective", "change_budget"}:
        updated = await apply_scope_change(state, record)
        state.clear()
        state.update(updated)
    elif intervention.type == "add_question":
        questions = state.setdefault("app:questions", [])
        next_index = len(questions)
        questions.append(
            {
                "question_id": f"q-user-{next_index}",
                "text": intervention.instruction,
                "priority": 1.0,
                "status": "pending",
                "perspective": "user_requested",
            }
        )
        state["app:questions_version"] = int(state.get("app:questions_version", 0)) + 1
    elif intervention.type == "challenge_claim":
        state.setdefault("app:contradictions", []).append(
            {
                "contradiction_id": f"ctr-api-{intervention.target_id or len(state.get('app:contradictions', []))}",
                "claim_ids": [intervention.target_id] if intervention.target_id else [],
                "resolution_status": "challenged",
                "instruction": intervention.instruction,
            }
        )

    await _persist_run(run_data)
    return {
        "status": "recorded",
        "run_id": run_id,
        "intervention_type": intervention.type,
        "message": f"Intervention '{intervention.type}' recorded for run {run_id}",
    }


@app.post("/v1/research-runs/{run_id}/approvals/{approval_id}")
async def submit_approval(run_id: str, approval_id: str, request: ApprovalActionRequest) -> dict[str, Any]:
    """Approve or reject a collaboration gate."""
    run_data = await _require_run(run_id)
    state = run_data.setdefault("state", {})
    decisions = state.setdefault("app:approval_decisions", {})
    decision = decisions.setdefault(approval_id, {"gate": approval_id, "required": True, "display_data": {}})
    decision["status"] = request.decision
    decision["rationale"] = request.rationale
    decision["approver_id"] = request.approver_id
    decision["decided_at"] = _now()
    state.setdefault("app:approval_inputs", {})[approval_id] = {"status": request.decision}
    run_data.setdefault("approvals", {})[approval_id] = decision
    await _persist_run(run_data)

    return {
        "run_id": run_id,
        "approval_id": approval_id,
        "status": request.decision,
        "rationale": request.rationale,
    }


@app.get("/v1/research-runs/{run_id}/approvals")
async def get_approvals(run_id: str) -> dict[str, Any]:
    """Return the current approval gate state for a run."""
    run_data = await _require_run(run_id)
    state = run_data.get("state", {})
    approvals = state.get("app:approval_decisions", run_data.get("approvals", {}))
    return {
        "run_id": run_id,
        "approvals": approvals if isinstance(approvals, dict) else {},
    }


@app.post("/v1/research-runs/{run_id}/exports")
async def export_report(run_id: str, format: str = "markdown") -> dict[str, Any]:
    """Export the final report in the requested format."""
    run_data = await _require_run(run_id)
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
