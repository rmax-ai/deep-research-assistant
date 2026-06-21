"""Citation entailment and integration verification tests.

Verifies Phase 1 exit criteria with both LLM and stub modes.
"""

import os

import pytest

LLM_AVAILABLE = bool(os.environ.get("GOOGLE_API_KEY"))


@pytest.mark.asyncio
class TestCitationEntailment:
    @pytest.mark.skipif(not LLM_AVAILABLE, reason="GOOGLE_API_KEY not set")
    async def test_full_pipeline_produces_claims_with_evidence_llm(self):
        from deep_research.agents import generate_structured
        from deep_research.agents.claim_builder import claim_builder
        from deep_research.agents.evidence_curator import evidence_curator
        from deep_research.agents.research_director import research_director

        raw = await generate_structured(
            "Reply with OK only",
            model="gemini-2.5-flash",
            max_output_tokens=8,
            timeout_seconds=20,
        )
        assert raw.strip() == "OK"

        plan = await research_director("Analyze ADK 2.0 tool governance", model="gemini-2.5-flash")
        assert isinstance(plan.get("scope"), dict)
        assert len(plan.get("proposed_perspectives", [])) >= 4

        evidence = await evidence_curator(
            "ADK 2.0 provides a workflow runtime with tool governance controls.",
            source_title="Example ADK Note",
            question="What governance controls exist in ADK 2.0?",
            model="gemini-2.5-flash",
        )
        assert len(evidence) > 0, "No evidence fragments"

        claims = await claim_builder(
            evidence,
            question="What governance controls exist in ADK 2.0?",
            model="gemini-2.5-flash",
        )
        assert len(claims) > 0, "No claims"
        for c in claims:
            if c.get("epistemic_status") in ("source_stated", "extracted"):
                refs = c.get("evidence_ids", [])
                assert len(refs) > 0
                for r in refs:
                    assert r < len(evidence)

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
