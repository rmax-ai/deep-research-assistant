"""Demo workflow tests for single-pass and iterative behavior."""

from __future__ import annotations

from typing import Any

import pytest


async def _run_demo(monkeypatch: pytest.MonkeyPatch, *, iterative_enabled: bool) -> dict[str, Any]:
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

    state = get_state().copy()
    reset_state()
    return state


@pytest.mark.asyncio
class TestEndToEndDemo:
    async def test_single_pass_mode_stays_single_cycle(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(monkeypatch, iterative_enabled=False)
        assert len(state["app:cycle_history"]) == 1
        assert len(state["app:claims"]) >= 1

    async def test_iterative_mode_runs_multiple_cycles(self, monkeypatch: pytest.MonkeyPatch):
        state = await _run_demo(monkeypatch, iterative_enabled=True)
        assert len(state["app:cycle_history"]) >= 2

    async def test_iterative_mode_produces_more_claims_than_single_pass(self, monkeypatch: pytest.MonkeyPatch):
        single_pass_state = await _run_demo(monkeypatch, iterative_enabled=False)
        iterative_state = await _run_demo(monkeypatch, iterative_enabled=True)
        assert len(iterative_state["app:claims"]) > len(single_pass_state["app:claims"])
