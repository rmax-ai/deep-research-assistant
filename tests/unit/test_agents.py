"""Unit tests for agent helpers and heuristics."""

from __future__ import annotations

import time
from types import SimpleNamespace

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

        result = await moderator(
            {
                "questions": [],
                "claims": [],
                "contradictions": [],
                "recent_cycle_history": [
                    {"novelty_score": 0.05},
                    {"novelty_score": 0.03},
                    {"novelty_score": 0.08},
                ],
            }
        )

        assert result["stagnation_detected"] is True
        assert any(action["type"] == "introduce_question_type" for action in result["rebalance_actions"])

    @pytest.mark.asyncio
    async def test_flags_missing_adversarial_evidence(self):
        from deep_research.agents.moderator import moderator

        result = await moderator(
            {
                "questions": [],
                "claims": [
                    {"claim_id": "c-1", "text": "Important claim", "materiality": "high"},
                ],
                "contradictions": [],
                "recent_cycle_history": [],
            }
        )

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

        result = await moderator(
            {
                "questions": questions,
                "claims": [],
                "contradictions": [],
                "recent_cycle_history": [],
            }
        )

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


class TestKnowledgeOrganizer:
    @pytest.mark.asyncio
    async def test_projects_topic_graph_from_questions_claims_and_evidence(self):
        from deep_research.agents.knowledge_organizer import knowledge_organizer

        concept_map = await knowledge_organizer(
            questions=[
                {"question_id": "q-1", "text": "How does approval work?", "perspective": "governance"},
                {"question_id": "q-2", "text": "How are budgets enforced?", "perspective": "governance"},
            ],
            claims=[
                {"claim_id": "c-1", "question_id": "q-1"},
                {"claim_id": "c-2", "question_id": "q-2"},
            ],
            evidence=[
                {"evidence_id": "e-1", "question_id": "q-1"},
                {"evidence_id": "e-2", "question_id": "q-2"},
            ],
        )

        assert concept_map["version"] == 1
        assert any(node["type"] == "perspective" for node in concept_map["topic_nodes"])
        assert any(node["type"] == "concept" and node["questions"] == ["q-1"] for node in concept_map["topic_nodes"])
        assert any(edge["relation"] == "contains" for edge in concept_map["edges"])


class TestAgentInit:
    async def test_is_llm_available(self):
        from deep_research.agents import is_llm_available

        assert isinstance(is_llm_available(), bool)

    def test_get_model_for_tier_uses_settings(self, monkeypatch: pytest.MonkeyPatch):
        from deep_research.agents import get_model_for_tier
        from deep_research.settings import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings.models.fast, "model", "gemini-fast-test")
        monkeypatch.setattr(settings.models.reasoning, "model", "gemini-reasoning-test")
        monkeypatch.setattr(settings.models.verification, "model", "gemini-verification-test")

        assert get_model_for_tier("fast") == "gemini-fast-test"
        assert get_model_for_tier("reasoning") == "gemini-reasoning-test"
        assert get_model_for_tier("verification") == "gemini-verification-test"

    def test_parse_json_code_fenced(self):
        from deep_research.agents import parse_json_response

        assert parse_json_response('```json\n{"key": "value"}\n```') == {"key": "value"}

    def test_parse_json_invalid_returns_default(self):
        from deep_research.agents import parse_json_response

        assert parse_json_response("not json", default={"fallback": True}) == {"fallback": True}

    @pytest.mark.asyncio
    async def test_generate_structured_falls_back_to_candidate_parts(self, monkeypatch: pytest.MonkeyPatch):
        from deep_research.agents import generate_structured

        class FakeModels:
            @staticmethod
            def generate_content(*args, **kwargs):
                return SimpleNamespace(
                    text=None,
                    candidates=[
                        SimpleNamespace(
                            content=SimpleNamespace(parts=[SimpleNamespace(text="OK from parts")])
                        )
                    ],
                )

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setattr("deep_research.agents.get_client", lambda: SimpleNamespace(models=FakeModels()))

        result = await generate_structured("Say OK", timeout_seconds=1)
        assert result == "OK from parts"

    @pytest.mark.asyncio
    async def test_generate_structured_times_out(self, monkeypatch: pytest.MonkeyPatch):
        from deep_research.agents import generate_structured

        class SlowModels:
            @staticmethod
            def generate_content(*args, **kwargs):
                time.sleep(0.2)
                return SimpleNamespace(text="late")

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setattr("deep_research.agents.get_client", lambda: SimpleNamespace(models=SlowModels()))

        with pytest.raises(RuntimeError, match="timed out"):
            await generate_structured("Say OK", timeout_seconds=0.01)

    @pytest.mark.asyncio
    async def test_generate_structured_retries_when_json_is_truncated(self, monkeypatch: pytest.MonkeyPatch):
        from deep_research.agents import generate_structured

        calls: list[dict[str, object]] = []

        class RetryModels:
            @staticmethod
            def generate_content(*args, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    return SimpleNamespace(text='```json\n{"questions": [\n  {"text": "A"')
                return SimpleNamespace(text='{"questions": [{"text": "A"}]}')

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setattr("deep_research.agents.get_client", lambda: SimpleNamespace(models=RetryModels()))

        result = await generate_structured("Generate questions", max_output_tokens=128, timeout_seconds=1)

        assert result == '{"questions": [{"text": "A"}]}'
        assert len(calls) == 2
        assert calls[0]["config"]["max_output_tokens"] == 128
        assert calls[1]["config"]["max_output_tokens"] == 256

    def test_parse_json_detects_truncated_fence_as_invalid(self):
        from deep_research.agents import parse_json_response

        assert parse_json_response('```json\n{"questions": [\n  {"text": "A"') == {}
