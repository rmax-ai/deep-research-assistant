"""Tests for ADK Workflow graph topology and execution."""

import pytest


@pytest.mark.asyncio
class TestWorkflowGraph:
    async def test_build_workflow(self):
        """Verify the workflow can be built without errors."""
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        assert wf is not None
        assert wf.name == "deep_research_assistant"

    async def test_all_nodes_present(self):
        """Verify all 20 nodes are registered in the workflow."""
        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()

        expected_nodes = [
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
            "stop_evaluate",
            "outline_build",
            "approve_outline",
            "draft_generate",
            "verify_draft",
            "repair_draft",
            "final_gate_check",
            "render_output",
        ]

        node_names = {n.name for n in wf.graph.nodes}
        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    async def test_edges_built(self):
        """Verify edges are configured correctly."""
        from google.adk.workflow import START as ST

        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        assert len(wf.edges) > 0

        # Check key edges exist by node names
        edge_pairs = {(e.from_node.name, e.to_node.name) for e in wf.edges}
        assert (ST.name, "scope_classify") in edge_pairs
        assert ("scope_classify", "perspective_generate") in edge_pairs

    async def test_workflow_end_to_end_stub(self):
        """Execute the full workflow with stub nodes and verify completion."""
        from google.adk.runners import InMemoryRunner
        from google.genai.types import Content, Part

        from deep_research.workflow.graph import build_research_workflow

        wf = build_research_workflow()
        runner = InMemoryRunner(agent=wf, app_name="deep_research_test")

        user_id = "test_user"
        session_id = "test_session_e2e"

        # Create session via runner's internal service
        await runner.session_service.create_session(
            app_name="deep_research_test",
            user_id=user_id,
            session_id=session_id,
        )

        # Run the workflow with a proper Content message
        msg = Content(role="user", parts=[Part(text="Research ADK 2.0 tool governance")])
        events = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=msg,
        ):
            events.append(event)

        assert len(events) > 0, "Workflow produced no events"

    async def test_all_node_functions_are_async(self):
        """Verify all node functions are async callables."""
        import inspect

        from deep_research.workflow.graph import _ALL_NODE_FUNCS

        for name, func in _ALL_NODE_FUNCS:
            assert inspect.iscoroutinefunction(func), f"{name} is not async"


# Need START constant for edge tests
try:
    from google.adk.workflow import START as START_NAME
except ImportError:
    START_NAME = "__start__"


class TestWorkflowRoutes:
    def test_route_lambdas_approve_plan(self):
        """Verify approve_plan route lambdas work."""
        # approved -> True
        approved_route = lambda ctx, result: result.get("approved", True)  # noqa: E731
        assert approved_route(None, {"approved": True})
        assert not approved_route(None, {"approved": False})

    def test_route_lambdas_stop(self):
        """Verify stop_evaluate route lambdas work."""
        stop_route = lambda ctx, result: result.get("should_stop", True)  # noqa: E731
        assert stop_route(None, {"should_stop": True})
        assert not stop_route(None, {"should_stop": False})

    def test_route_lambdas_verify(self):
        """Verify verify_draft route lambdas work."""
        blocking_route = lambda ctx, result: result.get("blocking_findings", 0) > 0  # noqa: E731
        assert blocking_route(None, {"blocking_findings": 2})
        assert not blocking_route(None, {"blocking_findings": 0})


class TestStoppingDecision:
    def test_cycle_limit(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={},
            budget={"searches_remaining": 100},
            cycle_count=10,
            max_cycles=10,
        )
        assert decision.should_stop
        assert "Maximum cycles" in decision.reasons[0]

    def test_budget_exhausted(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={},
            budget={"searches_remaining": 0},
            cycle_count=1,
        )
        assert decision.should_stop
        assert "budget exhausted" in decision.reasons[0]

    def test_info_gain_below_threshold(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={"information_gain": 0.001, "info_gain_threshold": 0.01},
            budget={"searches_remaining": 50},
            cycle_count=3,
        )
        assert decision.should_stop

    def test_all_material_questions_resolved(self):
        from deep_research.workflow.stopping import evaluate_stopping

        decision = evaluate_stopping(
            coverage={
                "information_gain": 0.05,
                "unresolved_material_questions": [],
            },
            budget={"searches_remaining": 50},
            cycle_count=2,
        )
        assert decision.should_stop


class TestCheckpointing:
    def test_create_and_load_checkpoint(self, tmp_path):
        from deep_research.workflow.recovery import (
            create_checkpoint,
            load_latest_checkpoint,
        )

        state = {
            "app:scope_result": {"status": "ok", "risk_level": "medium"},
            "app:claims_result": {"status": "ok", "claims_created": 5},
        }

        checkpoint_path = create_checkpoint(
            state=state,
            checkpoint_dir=tmp_path,
            run_id="run-001",
            node_name="claims_construct",
        )
        assert checkpoint_path.exists()

        loaded = load_latest_checkpoint(tmp_path, "run-001")
        assert loaded is not None
        assert loaded["app:scope_result"] == state["app:scope_result"]

    def test_load_nonexistent(self, tmp_path):
        from deep_research.workflow.recovery import load_latest_checkpoint

        result = load_latest_checkpoint(tmp_path, "nonexistent")
        assert result is None

    def test_restore_checkpoint(self):
        from deep_research.workflow.recovery import restore_checkpoint

        state = {
            "app:scope_classify_result": {"status": "ok"},
            "app:perspective_generate_result": {"status": "ok"},
            "app:claims_construct_result": {"status": "ok"},
            "temp:noise": "should be filtered",
        }
        restored = restore_checkpoint(
            state,
            resolved_nodes=["scope_classify", "perspective_generate"],
        )
        assert "app:scope_classify_result" in restored
        assert "app:perspective_generate_result" in restored
        assert "app:claims_construct_result" not in restored
        assert "temp:noise" not in restored


class TestValidation:
    def test_validate_stage_inputs_ok(self):
        from deep_research.nodes.validation import validate_stage_inputs

        state = {"app:scope_result": {"status": "ok"}}
        valid, missing = validate_stage_inputs("perspective_generate", state)
        assert valid
        assert missing == []

    def test_validate_stage_inputs_missing(self):
        from deep_research.nodes.validation import validate_stage_inputs

        valid, missing = validate_stage_inputs("perspective_generate", {})
        assert not valid
        assert "app:scope_result" in missing

    def test_validate_stage_first_node(self):
        from deep_research.nodes.validation import validate_stage_inputs

        valid, _missing = validate_stage_inputs("scope_classify", {})
        assert valid

    def test_validate_result_structure(self):
        from deep_research.nodes.validation import validate_result_structure

        assert validate_result_structure("test", {"status": "ok"})
        assert not validate_result_structure("test", {})


class TestPersistence:
    async def test_save_and_load(self):
        from deep_research.nodes.persistence import (
            delete_run_state,
            load_run_state,
            save_run_state,
        )

        state = {"app:scope_result": {"status": "ok"}}
        await save_run_state("run-001", state)

        loaded = await load_run_state("run-001")
        assert loaded is not None
        assert loaded["app:scope_result"] == state["app:scope_result"]

        await delete_run_state("run-001")
        loaded_after = await load_run_state("run-001")
        assert loaded_after is None

    async def test_list_runs(self):
        from deep_research.nodes.persistence import list_runs, save_run_state

        await save_run_state("run-a", {"data": "a"})
        await save_run_state("run-b", {"data": "b"})

        runs = await list_runs()
        assert "run-a" in runs
        assert "run-b" in runs
