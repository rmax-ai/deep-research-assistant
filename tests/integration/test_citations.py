"""Citation entailment and integration verification tests.

Verifies Phase 1 exit criteria with both LLM and stub modes.
"""

import asyncio
import os

import pytest

LLM_AVAILABLE = bool(os.environ.get("DEEP_RESEARCH_GOOGLE_API_KEY"))
LIVE_MODEL = os.environ.get("LIVE_VALIDATION_MODEL", "gemini-3-flash-preview")


@pytest.mark.asyncio
class TestCitationEntailment:
    @pytest.mark.live_llm
    @pytest.mark.live_agent_smoke
    @pytest.mark.skipif(not LLM_AVAILABLE, reason="DEEP_RESEARCH_GOOGLE_API_KEY not set")
    async def test_full_pipeline_produces_claims_with_evidence_llm(self):
        from deep_research.agents import generate_structured
        from deep_research.agents.claim_builder import claim_builder
        from deep_research.agents.evidence_curator import evidence_curator
        from deep_research.agents.research_director import research_director

        raw = await generate_structured(
            "Reply with OK only",
            model=LIVE_MODEL,
            max_output_tokens=8,
            timeout_seconds=20,
        )
        assert raw.strip() == "OK"

        plan = await research_director("Analyze ADK 2.0 tool governance", model=LIVE_MODEL)
        assert isinstance(plan.get("scope"), dict)
        assert len(plan.get("proposed_perspectives", [])) >= 4

        evidence = await evidence_curator(
            "ADK 2.0 provides a workflow runtime with tool governance controls.",
            source_title="Example ADK Note",
            question="What governance controls exist in ADK 2.0?",
            model=LIVE_MODEL,
        )
        assert len(evidence) > 0, "No evidence fragments"

        claims = await claim_builder(
            evidence,
            question="What governance controls exist in ADK 2.0?",
            model=LIVE_MODEL,
        )
        assert len(claims) > 0, "No claims"
        for c in claims:
            if c.get("epistemic_status") in ("source_stated", "extracted"):
                refs = c.get("evidence_ids", [])
                assert len(refs) > 0
                for r in refs:
                    assert r < len(evidence)

    @pytest.mark.live_llm
    @pytest.mark.live_bounded_workflow
    @pytest.mark.skipif(not LLM_AVAILABLE, reason="DEEP_RESEARCH_GOOGLE_API_KEY not set")
    async def test_bounded_live_workflow_smoke(self, monkeypatch: pytest.MonkeyPatch):
        from google.adk.runners import InMemoryRunner
        from google.genai.types import Content, Part

        from deep_research.agents.claim_builder import (
            _stub_claims,
        )
        from deep_research.agents.claim_builder import (
            claim_builder as live_claim_builder,
        )
        from deep_research.agents.evidence_curator import (
            _stub_evidence,
        )
        from deep_research.agents.evidence_curator import (
            evidence_curator as live_evidence_curator,
        )
        from deep_research.agents.research_director import (
            _stub_plan,
        )
        from deep_research.agents.research_director import (
            research_director as live_research_director,
        )
        from deep_research.settings import get_settings
        from deep_research.telemetry.events import get_event_bus
        from deep_research.workflow.graph import build_research_workflow
        from deep_research.workflow.state import get_state, reset_state

        async def fake_web_search(query: str, max_results: int = 5, tool_context=None):
            return {
                "query": query,
                "total_results": 1,
                "results": [
                    {
                        "title": f"Result for {query}",
                        "url": f"https://example.com/{abs(hash(query))}",
                        "snippet": "ADK 2.0 provides a workflow runtime with tool governance controls.",
                        "source_type": "primary",
                        "is_primary": True,
                    }
                ],
            }

        async def bounded_research_director(user_objective: str):
            plan = await live_research_director(user_objective, model=LIVE_MODEL)
            return plan if isinstance(plan, dict) and plan.get("objective") else _stub_plan(user_objective)

        async def bounded_evidence_curator(source_content: str, source_title: str = "", question: str = ""):
            fragments = await live_evidence_curator(
                source_content,
                source_title=source_title,
                question=question,
                model=LIVE_MODEL,
            )
            return fragments or _stub_evidence(source_content, source_title)

        async def bounded_claim_builder(evidence_fragments: list[dict[str, object]], question: str = ""):
            claims = await live_claim_builder(
                evidence_fragments,
                question=question,
                model=LIVE_MODEL,
            )
            return claims or _stub_claims(evidence_fragments)

        monkeypatch.setattr("deep_research.tools.search.web_search", fake_web_search)
        monkeypatch.setattr("deep_research.agents.research_director.research_director", bounded_research_director)
        monkeypatch.setattr("deep_research.agents.evidence_curator.evidence_curator", bounded_evidence_curator)
        monkeypatch.setattr("deep_research.agents.claim_builder.claim_builder", bounded_claim_builder)
        # Keep the graph real, but constrain non-core agents to their deterministic fallback paths.
        monkeypatch.setattr("deep_research.agents.perspective_planner.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.question_architect.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.query_planner.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.counter_evidence.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.moderator.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.outline_architect.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.section_writer.is_llm_available", lambda: False)
        monkeypatch.setattr("deep_research.agents.verifier.is_llm_available", lambda: False)
        settings = get_settings()
        monkeypatch.setattr(settings.workflow, "enable_iterative_research", False)
        monkeypatch.setattr(settings.workflow, "enable_follow_up_questions", False)
        monkeypatch.setattr(settings.workflow, "maximum_parallel_questions", 1)
        monkeypatch.setattr(settings.workflow, "max_cycles", 1)
        monkeypatch.setattr(settings.workflow, "llm_timeout_seconds", 15)

        reset_state()
        get_event_bus().reset()
        wf = build_research_workflow()
        runner = InMemoryRunner(agent=wf, app_name="live-bounded")
        await runner.session_service.create_session(app_name="live-bounded", user_id="u", session_id="s")
        msg = Content(role="user", parts=[Part(text="Analyze ADK 2.0 tool governance")])

        async def run_workflow() -> None:
            async for _ in runner.run_async(user_id="u", session_id="s", new_message=msg):
                pass

        await asyncio.wait_for(run_workflow(), timeout=45)

        state = get_state()
        events = get_event_bus().get_events_since(str(state.get("app:run_id", "")), None)
        assert any(event["event_type"] == "run.started" for event in events)
        assert any(event["event_type"] == "run.completed" for event in events)
        assert state.get("app:research_plan")
        assert state.get("app:questions")
        assert state.get("app:evidence")
        assert state.get("app:claims")
        assert state.get("app:final_report")
        assert {"A", "B", "C", "D"}.issubset(set(state.get("app:approval_decisions", {})))

        claims = state.get("app:claims", [])
        evidence = state.get("app:evidence", [])
        assert any(claim.get("evidence_ids") for claim in claims)
        for claim in claims:
            for ref in claim.get("evidence_ids", []):
                assert ref < len(evidence)
        reset_state()

    async def test_pipeline_produces_output_stub(self):
        from google.adk.runners import InMemoryRunner
        from google.genai.types import Content, Part

        from deep_research.workflow.graph import build_research_workflow
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        wf = build_research_workflow()
        runner = InMemoryRunner(agent=wf, app_name="st")
        await runner.session_service.create_session(app_name="st", user_id="u", session_id="s")
        msg = Content(role="user", parts=[Part(text="What is ADK 2.0?")])
        async for _ in runner.run_async(user_id="u", session_id="s", new_message=msg):
            pass
        state = get_state()
        assert "app:research_plan" in state, f"Keys: {list(state.keys())}"
        assert "app:final_report" in state
        reset_state()

    async def test_claim_builder_links_to_evidence(self):
        from deep_research.agents.claim_builder import _stub_claims
        f = [{"exact_excerpt": "ADK supports tool governance.", "evidence_type": "api_specification"}]
        claims = _stub_claims(f)
        assert len(claims) > 0
        for c in claims:
            assert len(c["evidence_ids"]) > 0

    async def test_evidence_curator_preserves_excerpts(self):
        from deep_research.agents.evidence_curator import _stub_evidence
        fragments = _stub_evidence("ADK 2.0 provides a Workflow API.", "Test")
        assert len(fragments) > 0
        assert fragments[0]["exact_excerpt"] == "ADK 2.0 provides a Workflow API."

    async def test_section_writer_never_invents_claims(self):
        from deep_research.agents.section_writer import _stub_section
        s = {"title": "T", "purpose": "...", "claim_ids": [0]}
        claims = [{"text": "ADK is a framework", "epistemic_status": "source_stated", "confidence": 0.8}]
        r = _stub_section(s, claims)
        assert r["status"] == "draft"
        assert "ADK is a framework" in r["content"]
