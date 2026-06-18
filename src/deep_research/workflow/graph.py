"""Deep Research Assistant — ADK 2.0 Workflow Graph.

Phase 0: Sequential pipeline with 20 stub nodes.
Branching (approval gates, stop loops, verify loops) added in Phase 2+.
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.agents.context import Context
from google.adk.workflow import START, Edge, FunctionNode, Workflow

logger = logging.getLogger(__name__)


# ── Node implementations (Phase 0 stubs) ───────────────────────────────────

async def scope_classify(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("scope_classify")
    return {"risk_level": "medium", "message": "Scope classification stub"}


async def perspective_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("perspective_generate")
    return {"perspective_count": 5, "message": "Perspective generation stub"}


async def question_graph_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("question_graph_build")
    return {"question_count": 0, "message": "Question graph stub"}


async def approve_plan(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("approve_plan (auto-approved)")
    return {"approved": True, "message": "Plan auto-approved"}


async def scheduler_select(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("scheduler_select")
    return {"next_question_id": None, "message": "No questions — skipping loop"}


async def search_plan_create(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("search_plan_create")
    return {"query_count": 0, "message": "Search plan stub"}


async def source_retrieve(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("source_retrieve")
    return {"sources_found": 0, "message": "Source retrieval stub"}


async def source_policy_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("source_policy_apply")
    return {"accepted": 0, "rejected": 0, "message": "Source policy stub"}


async def evidence_extract(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("evidence_extract")
    return {"fragments": 0, "message": "Evidence extraction stub"}


async def claims_construct(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("claims_construct")
    return {"claims_created": 0, "message": "Claims construction stub"}


async def contradictions_search(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("contradictions_search")
    return {"contradictions_found": 0, "message": "Contradiction search stub"}


async def coverage_calculate(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("coverage_calculate")
    return {"primary_source_coverage": 0.0, "information_gain": 0.0}


async def stop_evaluate(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("stop_evaluate (auto-stop)")
    return {"should_stop": True, "reason": "No evidence collected"}


async def outline_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("outline_build")
    return {"section_count": 3, "message": "Outline stub"}


async def approve_outline(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("approve_outline (auto-approved)")
    return {"approved": True, "message": "Outline auto-approved"}


async def draft_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("draft_generate")
    return {"sections_drafted": 3, "message": "Draft generation stub"}


async def verify_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("verify_draft (no findings)")
    return {"blocking_findings": 0, "passed": True, "message": "Verification stub — all clear"}


async def repair_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("repair_draft (not needed, but wired)")
    return {"issues_repaired": 0, "message": "Repair stub — nothing to fix"}


async def final_gate_check(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("final_gate_check (auto-approved)")
    return {"approved": True, "message": "Final gate auto-approved"}


async def render_output(ctx: Context, node_input: Any) -> dict[str, Any]:
    logger.info("render_output — pipeline complete!")
    return {"output_format": "markdown", "message": "Pipeline skeleton complete"}


# ── Node registry ─────────────────────────────────────────────────────────

_ALL_NODE_FUNCS: list[tuple[str, Any]] = [
    ("scope_classify", scope_classify),
    ("perspective_generate", perspective_generate),
    ("question_graph_build", question_graph_build),
    ("approve_plan", approve_plan),
    ("scheduler_select", scheduler_select),
    ("search_plan_create", search_plan_create),
    ("source_retrieve", source_retrieve),
    ("source_policy_apply", source_policy_apply),
    ("evidence_extract", evidence_extract),
    ("claims_construct", claims_construct),
    ("contradictions_search", contradictions_search),
    ("coverage_calculate", coverage_calculate),
    ("stop_evaluate", stop_evaluate),
    ("outline_build", outline_build),
    ("approve_outline", approve_outline),
    ("draft_generate", draft_generate),
    ("verify_draft", verify_draft),
    ("repair_draft", repair_draft),
    ("final_gate_check", final_gate_check),
    ("render_output", render_output),
]


# ── Edge builder (sequential, no branching in Phase 0) ────────────────────

def _build_edges(nodes: dict[str, FunctionNode]) -> list[Edge]:
    """Build sequential edges through all 20 nodes (no branching in Phase 0)."""
    n = nodes
    edges: list[Edge] = []

    # Full sequential pipeline — all unconditional edges
    sequence = [
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

    edges.append(Edge(from_node=START, to_node=n[sequence[0]]))
    for i in range(len(sequence) - 1):
        edges.append(Edge(from_node=n[sequence[i]], to_node=n[sequence[i + 1]]))

    return edges


# ── Workflow builder ──────────────────────────────────────────────────────

def build_research_workflow() -> Workflow:
    """Build the complete 20-node sequential research workflow.

    Returns:
        Configured ADK 2.0 Workflow ready for InMemoryRunner.
    """
    node_list = [FunctionNode(func=func, name=name) for name, func in _ALL_NODE_FUNCS]
    nodes = {n.name: n for n in node_list}
    edges = _build_edges(nodes)

    return Workflow(
        name="deep_research_assistant",
        description=(
            "Enterprise-grade governed research runtime. "
            "Converts broad research requests into inspectable, "
            "evidence-backed workflows with claim-level traceability."
        ),
        nodes=node_list,
        edges=edges,
    )
