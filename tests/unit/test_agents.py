"""Unit tests for agent helpers and heuristics."""

from __future__ import annotations

import pytest


class TestResearchDirector:
    async def test_stub_plan_when_no_llm(self):
        from deep_research.agents.research_director import _stub_plan

        plan = _stub_plan("Analyze ADK 2.0 security")
        assert "objective" in plan
        assert plan["objective"]["title"] == "Analyze ADK 2.0 security"

    async def test_research_director_without_api_key(self):
        from deep_research.agents.research_director import research_director

        plan = await research_director("Analyze something")
        assert "objective" in plan
        assert plan["scope"]["assumptions"][0]["text"] == "LLM unavailable — stub plan generated"


class TestModerator:
    @pytest.mark.asyncio
    async def test_detects_stagnation_after_three_low_novelty_cycles(self):
        from deep_research.agents.moderator import moderator

        result = await moderator({
            "questions": [],
            "claims": [],
            "contradictions": [],
            "recent_cycle_history": [
                {"novelty_score": 0.05},
                {"novelty_score": 0.03},
                {"novelty_score": 0.08},
            ],
        })

        assert result["stagnation_detected"] is True
        assert any(action["type"] == "introduce_question_type" for action in result["rebalance_actions"])

    @pytest.mark.asyncio
    async def test_flags_missing_adversarial_evidence(self):
        from deep_research.agents.moderator import moderator

        result = await moderator({
            "questions": [],
            "claims": [
                {"claim_id": "c-1", "text": "Important claim", "materiality": "high"},
            ],
            "contradictions": [],
            "recent_cycle_history": [],
        })

        assert any(action["type"] == "add_counter_evidence" for action in result["rebalance_actions"])

    @pytest.mark.asyncio
    async def test_detects_perspective_imbalance(self):
        from deep_research.agents.moderator import moderator

        questions = [
            {"question_id": "q-1", "text": "A", "perspective": "architecture", "priority": 0.7},
            {"question_id": "q-2", "text": "B", "perspective": "architecture", "priority": 0.7},
            {"question_id": "q-3", "text": "C", "perspective": "architecture", "priority": 0.7},
            {"question_id": "q-4", "text": "D", "perspective": "skeptical", "priority": 0.5},
        ]

        result = await moderator({
            "questions": questions,
            "claims": [],
            "contradictions": [],
            "recent_cycle_history": [],
        })

        assert any(action["type"] == "rebalance_perspective" for action in result["rebalance_actions"])
        assert result["adjusted_priorities"]["q-1"] < 0.7
        assert result["adjusted_priorities"]["q-4"] > 0.5


class TestQuestionArchitect:
    @pytest.mark.asyncio
    async def test_generate_follow_up_links_parent_and_uses_evidence(self):
        from deep_research.agents.question_architect import generate_follow_ups

        follow_ups = await generate_follow_ups(
            evidence=[
                {
                    "source_id": "docs.example.com",
                    "normalized_statement": "Version 2.1 introduced signed tool manifests.",
                }
            ],
            parent_question={"question_id": "q-root", "text": "How does tool governance work?", "priority": 0.6},
            existing_questions=[],
        )

        assert follow_ups
        assert follow_ups[0]["parent_question_id"] == "q-root"
        assert "Version 2.1 introduced signed tool manifests"[:20] in follow_ups[0]["rationale"]

    @pytest.mark.asyncio
    async def test_generate_follow_up_deduplicates(self):
        from deep_research.agents.question_architect import generate_follow_ups

        existing = [{"text": "What does the evidence from docs.example.com imply about governance controls?"}]
        follow_ups = await generate_follow_ups(
            evidence=[{"source_id": "docs.example.com", "normalized_statement": "governance controls"}],
            parent_question={"question_id": "q-root", "text": "governance controls", "priority": 0.6},
            existing_questions=existing,
        )

        assert follow_ups == []


class TestAgentInit:
    async def test_is_llm_available(self):
        from deep_research.agents import is_llm_available

        assert isinstance(is_llm_available(), bool)

    def test_parse_json_code_fenced(self):
        from deep_research.agents import parse_json_response

        assert parse_json_response('```json\n{"key": "value"}\n```') == {"key": "value"}

    def test_parse_json_invalid_returns_default(self):
        from deep_research.agents import parse_json_response

        assert parse_json_response("not json", default={"fallback": True}) == {"fallback": True}
