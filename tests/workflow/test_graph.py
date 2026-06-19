"""Workflow and deterministic node tests for Phase 2."""

from __future__ import annotations

import pytest


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
            "scheduler_select",
            "search_plan_create",
            "source_retrieve",
            "source_policy_apply",
            "evidence_extract",
            "claims_construct",
            "contradictions_search",
            "coverage_calculate",
            "moderator",
            "stop_evaluate",
            "outline_build",
            "approve_outline",
            "draft_generate",
            "verify_draft",
            "repair_draft",
            "final_gate_check",
            "render_output",
        }
        assert expected.issubset(node_names)

    async def test_branching_edges_present(self):
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        edge_map = {(edge.from_node.name, edge.to_node.name, getattr(edge, "route", None)) for edge in wf.edges}

        assert ("approve_plan", "scheduler_select", True) in edge_map
        assert ("approve_plan", "scope_classify", False) in edge_map
        assert ("stop_evaluate", "scheduler_select", False) in edge_map
        assert ("stop_evaluate", "outline_build", True) in edge_map


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
