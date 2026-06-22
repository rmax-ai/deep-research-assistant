"""Workflow and deterministic node tests for Phase 3."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deep_research.exceptions import ApprovalRequiredError


@pytest.mark.asyncio
class TestWorkflowGraph:
    async def test_build_workflow(self):
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        assert wf.name == "deep_research_assistant"

    async def test_all_nodes_present(self):
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        node_names = {node.name for node in wf.graph.nodes}
        expected = {
            "scope_classify",
            "perspective_generate",
            "question_graph_build",
            "approve_plan",
            "plan_not_required",
            "scheduler_select",
            "search_plan_create",
            "source_retrieve",
            "source_policy_apply",
            "evidence_extract",
            "claims_construct",
            "knowledge_organize",
            "contradictions_search",
            "coverage_calculate",
            "moderator",
            "interventions_apply",
            "scope_change_apply",
            "stop_evaluate",
            "outline_build",
            "approve_outline",
            "outline_not_required",
            "draft_generate",
            "verify_draft",
            "repair_draft",
            "final_gate_check",
            "publication_not_required",
            "render_output",
        }
        assert expected.issubset(node_names)

    async def test_branching_edges_present(self):
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        edge_map = {(edge.from_node.name, edge.to_node.name, getattr(edge, "route", None)) for edge in wf.edges}

        assert ("approve_plan", "scope_classify", 0) in edge_map
        assert ("approve_plan", "scheduler_select", 1) in edge_map
        assert ("approve_plan", "plan_not_required", 2) in edge_map
        assert ("plan_not_required", "scheduler_select", None) in edge_map
        assert ("scope_change_apply", "question_graph_build", 1) in edge_map
        assert ("stop_evaluate", "scheduler_select", 0) in edge_map
        assert ("stop_evaluate", "outline_build", 1) in edge_map
        assert ("approve_outline", "outline_build", 0) in edge_map
        assert ("final_gate_check", "render_output", 1) in edge_map
        assert ("final_gate_check", "publication_not_required", 2) in edge_map

    async def test_approval_routing_uses_integer_routes(self):
        from deep_research.workflow.graph import approve_plan
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        state = get_state()
        state.update(
            {
                "app:scope": {"risk_level": "high"},
                "app:objective": {},
                "app:research_plan": {"approval_recommendation": {"scope_approval_required": True}},
                "app:approval_inputs": {"A": {"status": "approved"}, "B": {"status": "rejected"}},
            }
        )

        ctx = SimpleNamespace(route=None)
        result = await approve_plan(ctx, None)
        assert ctx.route == 0
        assert result["status"] == "rejected"

    async def test_approve_plan_pauses_when_required_approval_is_missing(self, monkeypatch: pytest.MonkeyPatch):
        from deep_research.settings import get_settings
        from deep_research.workflow.graph import approve_plan
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        settings = get_settings()
        monkeypatch.setattr(settings.approvals, "mode", "strict")
        monkeypatch.setattr(settings.approvals, "scope_required_for_risk", "all")
        state = get_state()
        state.update(
            {
                "app:run_id": "run-approve",
                "app:scope": {"risk_level": "high"},
                "app:objective": {},
                "app:research_plan": {"approval_recommendation": {"scope_approval_required": True}},
                "app:approval_inputs": {},
                "app:enforce_approvals": True,
                "app:principal": {"tenant_id": "t", "user_id": "u", "run_id": "run-approve", "agent_role": "user"},
            }
        )

        with pytest.raises(ApprovalRequiredError):
            await approve_plan(SimpleNamespace(route=None), None)

    async def test_event_emission_in_nodes(self):
        from deep_research.telemetry.events import get_event_bus
        from deep_research.workflow.graph import render_output
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        bus = get_event_bus()
        bus.reset()
        state = get_state()
        state.update(
            {
                "app:run_id": "run-1",
                "app:objective": {"title": "Demo"},
                "app:drafts": [{"content": "Section body"}],
                "app:claims": [],
                "app:cycle_history": [],
            }
        )

        await render_output(SimpleNamespace(route=None), None)
        events = bus.get_events_since("run-1", None)
        assert any(event["event_type"] == "run.completed" for event in events)

    async def test_instrumented_nodes_emit_lifecycle_and_route_events(self):
        from deep_research.telemetry.events import get_event_bus
        from deep_research.workflow.graph import _instrument_node, scheduler_select
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        bus = get_event_bus()
        bus.reset()
        state = get_state()
        state.update(
            {
                "app:run_id": "run-node",
                "app:questions": [{"question_id": "q-1", "text": "A", "priority": 0.9, "status": "pending"}],
                "app:phase": "planning",
            }
        )
        instrumented = _instrument_node("scheduler_select", scheduler_select)
        await instrumented(SimpleNamespace(route=None), None)
        events = bus.get_events_since("run-node", None)
        event_types = [event["event_type"] for event in events]

        assert "node.started" in event_types
        assert "node.completed" in event_types

    async def test_stop_evaluate_emits_stop_event(self):
        from deep_research.telemetry.events import get_event_bus
        from deep_research.workflow.graph import stop_evaluate
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        bus = get_event_bus()
        bus.reset()
        state = get_state()
        state.update({"app:run_id": "run-stop", "app:phase": "researching"})

        await stop_evaluate(SimpleNamespace(route=None), None)
        events = bus.get_events_since("run-stop", None)
        stop_events = [event for event in events if event["event_type"] == "stop.evaluated"]
        assert stop_events
        assert "should_stop" in stop_events[-1]["payload"]

    async def test_scope_change_mid_run_routes_back_to_question_graph(self):
        from deep_research.workflow.graph import scope_change_apply
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        state = get_state()
        state.update(
            {
                "app:scope": {"included_topics": ["baseline"], "excluded_topics": []},
                "app:research_plan": {"proposed_budget": {}},
                "app:pending_scope_changes": [{"type": "add_topic", "topic": "security"}],
            }
        )

        ctx = SimpleNamespace(route=None)
        result = await scope_change_apply(ctx, None)
        assert ctx.route == 1
        assert result["applied"] == 1
        assert "security" in get_state()["app:scope"]["included_topics"]

    async def test_final_gate_rejection_stops_workflow_instead_of_repair_loop(self):
        from deep_research.workflow.graph import final_gate_check
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        state = get_state()
        state.update(
            {
                "app:verification": {"blocking_findings": 0, "findings": [], "passed": True},
                "app:drafts": [{"content": "Ready for publication"}],
                "app:objective": {"intended_audience": "external"},
                "app:approval_inputs": {"D": {"status": "rejected"}},
            }
        )

        ctx = SimpleNamespace(route=None)
        with pytest.raises(RuntimeError, match="Final publication approval was rejected"):
            await final_gate_check(ctx, None)

        assert ctx.route == 0
        assert state["app:phase"] == "failed"
        assert state["app:final_gate_result"]["status"] == "rejected"

    async def test_repair_draft_stops_after_max_passes(self):
        from deep_research.workflow.graph import repair_draft
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        state = get_state()
        state.update(
            {
                "app:verification": {
                    "blocking_findings": 1,
                    "findings": [{"severity": "blocking", "message": "Missing citation"}],
                },
                "app:repair_count": 2,
                "app:drafts": [{"content": "Draft"}],
            }
        )

        with pytest.raises(RuntimeError, match="Repair loop exceeded max passes"):
            await repair_draft(SimpleNamespace(route=None), None)

        assert state["app:phase"] == "failed"

    async def test_repair_draft_updates_verification_state_after_successful_repair(self):
        from deep_research.workflow.graph import repair_draft
        from deep_research.workflow.state import get_state, reset_state

        reset_state()
        state = get_state()
        state.update(
            {
                "app:verification": {
                    "blocking_findings": 1,
                    "major_findings": 0,
                    "findings": [{"severity": "blocking", "message": "Missing citation"}],
                    "passed": False,
                },
                "app:repair_count": 0,
                "app:drafts": [{"content": "Draft"}],
            }
        )

        result = await repair_draft(SimpleNamespace(route=None), None)

        assert result["remaining_blocking"] == 0
        assert state["app:verify_result"]["blocking_findings"] == 0
        assert state["app:verification"]["passed"] is True
        assert state["app:verification"]["findings"] == []


class TestScheduler:
    def test_highest_priority_question_selected(self):
        from deep_research.nodes.scheduler import select_frontier_questions

        questions = [
            {"question_id": "q-1", "text": "Low", "priority": 0.2, "risk_score": 0.1, "novelty_score": 0.1, "question_type": "descriptive", "status": "pending"},
            {"question_id": "q-2", "text": "High", "priority": 0.9, "risk_score": 0.9, "novelty_score": 0.8, "question_type": "security", "materiality": "high", "status": "pending"},
        ]

        result = select_frontier_questions(questions)
        assert result["selected_questions"][0]["question_id"] == "q-2"
        assert result["priorities"]["q-2"] > result["priorities"]["q-1"]

    def test_parallel_groups_separate_independent_questions(self):
        from deep_research.nodes.scheduler import select_frontier_questions

        questions = [
            {"question_id": "q-1", "text": "A", "priority": 0.8, "question_type": "descriptive", "status": "pending", "parent_question_ids": []},
            {"question_id": "q-2", "text": "B", "priority": 0.75, "question_type": "descriptive", "status": "pending", "parent_question_ids": []},
        ]

        result = select_frontier_questions(questions)
        assert any(len(group) >= 2 for group in result["parallel_groups"])


class TestStopping:
    def test_stops_on_budget_exhaustion(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={},
            budget_remaining={"searches_remaining": 0, "tokens_remaining": 10, "sources_remaining": 2},
            questions=[],
            claims=[],
            contradictions=[],
            cycle_history=[],
        )
        assert decision.should_stop is True
        assert "Budget exhausted" in decision.reasons

    def test_stops_on_low_information_gain(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={"marginal_information_gain": 0.01},
            budget_remaining={"searches_remaining": 10, "tokens_remaining": 10, "sources_remaining": 2},
            questions=[{"text": "A", "status": "resolved", "priority": 0.7}],
            claims=[],
            contradictions=[],
            cycle_history=[
                {"information_gain": 0.01},
                {"information_gain": 0.02},
                {"information_gain": 0.03},
            ],
        )
        assert decision.should_stop is True
        assert any("Marginal information gain" in reason for reason in decision.reasons)

    def test_continues_when_material_gaps_remain(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={"primary_source_coverage": 0.1},
            budget_remaining={"searches_remaining": 10, "tokens_remaining": 10, "sources_remaining": 2},
            questions=[{"text": "A", "status": "pending", "priority": 0.8}],
            claims=[],
            contradictions=[],
            cycle_history=[],
        )
        assert decision.should_stop is False


class TestBudget:
    def test_budget_enforcement_rejects_overage(self):
        from deep_research.nodes.budget import enforce_perspective_budget

        budgets = {
            "security": {
                "searches_remaining": 1,
                "tokens_remaining": 100,
                "sources_remaining": 1,
                "status": "active",
            }
        }
        result = enforce_perspective_budget("security", 2, budgets)
        assert result["accepted"] is False
        assert budgets["security"]["status"] == "budget_exhausted"

    def test_section_local_evidence_filtering(self):
        from deep_research.nodes.budget import filter_evidence_for_section

        claims = [
            {"claim_id": "c-1", "evidence_ids": ["e-1"]},
            {"claim_id": "c-2", "evidence_ids": ["e-2"]},
        ]
        evidence = [
            {"evidence_id": "e-1", "exact_excerpt": "Relevant"},
            {"evidence_id": "e-2", "exact_excerpt": "Irrelevant"},
        ]

        filtered = filter_evidence_for_section(["c-1"], claims, evidence)
        assert filtered == [{"evidence_id": "e-1", "exact_excerpt": "Relevant"}]
