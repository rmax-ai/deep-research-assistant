"""Tests for the Research Director agent."""

import pytest


class TestResearchDirector:
    async def test_stub_plan_when_no_llm(self):
        """Verify stub plan is returned when LLM is not available."""
        from deep_research.agents.research_director import _stub_plan

        plan = _stub_plan("Analyze ADK 2.0 security")
        assert "objective" in plan
        assert plan["objective"]["title"] == "Analyze ADK 2.0 security"
        assert len(plan["proposed_perspectives"]) == 4
        assert plan["proposed_perspectives"][0]["name"] == "foundational"

    async def test_stub_plan_empty_input(self):
        """Verify stub handles empty input gracefully."""
        from deep_research.agents.research_director import _stub_plan

        plan = _stub_plan("")
        assert plan["objective"]["title"] == "Untitled Research"

    async def test_stub_plan_structure(self):
        """Verify stub plan has all required top-level keys."""
        from deep_research.agents.research_director import _stub_plan

        plan = _stub_plan("Research topic")
        required_keys = {
            "objective",
            "scope",
            "proposed_perspectives",
            "completion_criteria",
            "proposed_budget",
            "approval_recommendation",
        }
        assert required_keys.issubset(set(plan.keys()))

    async def test_research_director_without_api_key(self):
        """Verify research_director falls back to stub without API key."""
        from deep_research.agents.research_director import research_director

        plan = await research_director("Analyze something")
        assert "objective" in plan
        # Should fall back to stub since GOOGLE_API_KEY likely not set
        assert plan["scope"]["assumptions"][0]["text"] == "LLM unavailable — stub plan generated"

    @pytest.mark.skipif(
        "not __import__('os').environ.get('GOOGLE_API_KEY')",
        reason="GOOGLE_API_KEY not set",
    )
    async def test_research_director_with_llm(self):
        """Test with actual LLM (requires GOOGLE_API_KEY)."""
        from deep_research.agents.research_director import research_director

        plan = await research_director(
            "Analyze the security implications of using AI agents for enterprise tool execution"
        )
        assert "objective" in plan
        assert plan["objective"]["title"]
        assert len(plan["proposed_perspectives"]) >= 3
        # Risk should be high for security topics
        assert plan["scope"]["risk_level"] in ("high", "critical")


class TestAgentInit:
    async def test_is_llm_available(self):
        from deep_research.agents import is_llm_available

        result = is_llm_available()
        assert isinstance(result, bool)

    def test_parse_json_code_fenced(self):
        from deep_research.agents import parse_json_response

        text = '```json\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_json_bare(self):
        from deep_research.agents import parse_json_response

        result = parse_json_response('{"a": 1, "b": [2, 3]}')
        assert result == {"a": 1, "b": [2, 3]}

    def test_parse_json_with_text_around(self):
        from deep_research.agents import parse_json_response

        text = 'Here is the result:\n\n{"x": "y"}\n\nHope this helps!'
        result = parse_json_response(text)
        assert result == {"x": "y"}

    def test_parse_json_invalid_returns_default(self):
        from deep_research.agents import parse_json_response

        result = parse_json_response("not json at all", default={"fallback": True})
        assert result == {"fallback": True}
