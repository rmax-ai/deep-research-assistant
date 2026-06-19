"""Demo workflow tests for collaborative behavior."""

from __future__ import annotations

from typing import Any

import pytest


async def _run_demo(
    monkeypatch: pytest.MonkeyPatch,
    *,
    iterative_enabled: bool,
    mode: str = "review_first",
    interventions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from google.adk.runners import InMemoryRunner
    from google.genai.types import Content, Part

    from deep_research.settings import get_settings
    from deep_research.workflow.graph import build_research_workflow
    from deep_research.workflow.state import get_state, reset_state

    async def fake_web_search(query: str, max_results: int = 5, tool_context: Any | None = None) -> dict[str, Any]:
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
    monkeypatch.setattr(settings.workflow, "enable_iterative_research", iterative_enabled)
    monkeypatch.setattr(settings.workflow, "enable_follow_up_questions", iterative_enabled)
    monkeypatch.setattr(settings.workflow, "max_cycles", 3)
    monkeypatch.setattr(settings.workflow, "maximum_parallel_questions", 1)

    reset_state()
    state = get_state()
    state["app:run_id"] = "demo-run"
    state["app:run_mode"] = mode
    state["app:approval_inputs"] = {
        "A": {"status": "approved"},
        "B": {"status": "approved"},
        "C": {"status": "approved"},
        "D": {"status": "approved"},
    }
    state["app:pending_interventions"] = interventions or []

    wf = build_research_workflow()
    runner = InMemoryRunner(agent=wf, app_name="deep_research_demo")
    await runner.session_service.create_session(
        app_name="deep_research_demo",
        user_id="demo_user",
        session_id="demo_session",
    )

    message = Content(role="user", parts=[Part(text="Research ADK 2.0 tool governance")])
    async for _event in runner.run_async(
        user_id="demo_user",
        session_id="demo_session",
        new_message=message,
    ):
        pass

    snapshot = get_state().copy()
    reset_state()
    return snapshot


@pytest.mark.asyncio
class TestEndToEndDemo:
    async def test_review_first_mode_records_all_four_gates(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(monkeypatch, iterative_enabled=False, mode="review_first")
        approvals = state["app:approval_decisions"]
        assert {"A", "B", "C", "D"}.issubset(set(approvals))
        assert all(approvals[gate]["status"] in ("approved", "not_required") for gate in ("A", "B", "C", "D"))

    async def test_single_pass_mode_stays_single_cycle(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(monkeypatch, iterative_enabled=False)
        assert len(state["app:cycle_history"]) == 1
        assert len(state["app:claims"]) >= 1

    async def test_iterative_mode_runs_multiple_cycles(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(monkeypatch, iterative_enabled=True)
        assert len(state["app:cycle_history"]) >= 2

    async def test_collaborative_mode_applies_user_intervention(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(
            monkeypatch,
            iterative_enabled=True,
            mode="collaborative",
            interventions=[{"type": "add_question", "instruction": "What are the audit tradeoffs?"}],
        )
        assert any(question["text"] == "What are the audit tradeoffs?" for question in state["app:questions"])
