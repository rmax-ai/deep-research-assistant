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
    """Classify and scope the research request using Research Director agent.

    Extracts the user's objective from node_input (the user message content),
    runs the Research Director LLM agent, and stores the plan in session state.
    """
    logger.info("scope_classify: running Research Director")

    # Extract user objective from the input
    user_text = ""
    if isinstance(node_input, dict):
        user_text = node_input.get("content", node_input.get("text", ""))
    elif isinstance(node_input, str):
        user_text = node_input
    elif hasattr(node_input, "parts"):
        # ADK genai.types.Content
        parts = getattr(node_input, "parts", [])
        user_text = " ".join(getattr(p, "text", "") for p in parts if hasattr(p, "text"))

    if not user_text:
        return {"status": "ok", "risk_level": "medium", "message": "No user input — using defaults"}

    from deep_research.agents.research_director import research_director

    plan = await research_director(user_text)

    # Store plan components in session state for downstream nodes
    ctx.session.state["app:research_plan"] = plan
    ctx.session.state["app:objective"] = plan.get("objective", {})
    ctx.session.state["app:scope"] = plan.get("scope", {})
    ctx.session.state["app:proposed_perspectives"] = plan.get("proposed_perspectives", [])

    return {
        "status": "ok",
        "risk_level": plan.get("scope", {}).get("risk_level", "medium"),
        "objective_title": plan.get("objective", {}).get("title", ""),
        "perspective_count": len(plan.get("proposed_perspectives", [])),
        "message": f"Research plan generated: {plan.get('objective', {}).get('title', 'Untitled')}",
    }


async def perspective_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Generate research perspectives using Perspective Planner agent.

    Reads scope and objective from session state, generates perspectives,
    stores them in session state.
    """
    logger.info("perspective_generate: running Perspective Planner")
    scope = ctx.session.state.get("app:scope", {})
    objective = ctx.session.state.get("app:objective", {})
    user_text = objective.get("primary_question", "")

    from deep_research.agents.perspective_planner import perspective_planner

    perspectives = await perspective_planner(scope, user_text)
    ctx.session.state["app:perspectives"] = perspectives
    return {"perspective_count": len(perspectives), "message": f"Generated {len(perspectives)} perspectives"}


async def question_graph_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build question graph using Question Architect agent."""
    logger.info("question_graph_build: running Question Architect")
    perspectives = ctx.session.state.get("app:perspectives", [])
    scope = ctx.session.state.get("app:scope", {})

    from deep_research.agents.question_architect import question_architect

    result = await question_architect(perspectives, scope)
    questions = result.get("questions", [])
    ctx.session.state["app:questions"] = questions
    return {"question_count": len(questions), "message": f"Generated {len(questions)} questions"}


async def search_plan_create(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Create search plans using Query Planner agent.

    Takes the first pending question from session state and generates queries.
    """
    logger.info("search_plan_create: running Query Planner")
    questions = ctx.session.state.get("app:questions", [])
    if not questions:
        return {"query_count": 0, "message": "No questions to plan searches for"}

    question = questions[0]  # Simple: take first question
    from deep_research.agents.query_planner import query_planner

    queries = await query_planner(question)
    ctx.session.state["app:search_queries"] = queries
    ctx.session.state["app:active_question"] = question
    return {"query_count": len(queries), "message": f"Generated {len(queries)} search queries"}


async def source_retrieve(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Retrieve sources using web search tool."""
    logger.info("source_retrieve: running web search")
    queries = ctx.session.state.get("app:search_queries", [])
    if not queries:
        return {"sources_found": 0, "message": "No queries to search"}

    from deep_research.tools.search import web_search

    all_results = []
    for q in queries[:3]:  # Limit to 3 queries
        result = await web_search(q.get("raw_query", ""), max_results=3)
        all_results.extend(result.get("results", []))

    ctx.session.state["app:sources"] = all_results
    return {"sources_found": len(all_results), "message": f"Retrieved {len(all_results)} sources"}


async def evidence_extract(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Extract evidence using Evidence Curator agent."""
    logger.info("evidence_extract: running Evidence Curator")
    sources = ctx.session.state.get("app:sources", [])
    question = ctx.session.state.get("app:active_question", {})

    if not sources:
        return {"fragments": 0, "message": "No sources to extract from"}

    from deep_research.agents.evidence_curator import evidence_curator

    all_fragments = []
    for src in sources[:2]:  # Limit to first 2 sources
        content = src.get("snippet", "")
        title = src.get("title", "Untitled")
        fragments = await evidence_curator(content, title, question.get("text", ""))
        # Add source_id to each fragment
        for f in fragments:
            f["source_id"] = src.get("url", "unknown")
        all_fragments.extend(fragments)

    ctx.session.state["app:evidence"] = all_fragments
    return {"fragments": len(all_fragments), "message": f"Extracted {len(all_fragments)} evidence fragments"}


async def claims_construct(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build claims using Claim Builder agent."""
    logger.info("claims_construct: running Claim Builder")
    evidence = ctx.session.state.get("app:evidence", [])
    question = ctx.session.state.get("app:active_question", {})

    if not evidence:
        return {"claims_created": 0, "message": "No evidence to build claims from"}

    from deep_research.agents.claim_builder import claim_builder

    claims = await claim_builder(evidence, question.get("text", ""))
    ctx.session.state["app:claims"] = claims
    return {"claims_created": len(claims), "message": f"Built {len(claims)} claims"}


async def outline_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build report outline using Outline Architect agent."""
    logger.info("outline_build: running Outline Architect")
    claims = ctx.session.state.get("app:claims", [])
    objective = ctx.session.state.get("app:objective", {})

    from deep_research.agents.outline_architect import outline_architect

    outline = await outline_architect(claims, objective)
    ctx.session.state["app:outline"] = outline
    return {"section_count": len(outline.get("sections", [])), "message": f"Built outline with {len(outline.get('sections', []))} sections"}


async def draft_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Generate section drafts using Section Writer agent."""
    logger.info("draft_generate: running Section Writer")
    outline = ctx.session.state.get("app:outline", {})
    claims = ctx.session.state.get("app:claims", [])

    if not outline.get("sections"):
        return {"sections_drafted": 0, "message": "No outline sections to draft"}

    from deep_research.agents.section_writer import section_writer

    drafts = []
    for section in outline["sections"][:2]:  # Draft first 2 sections
        draft = await section_writer(section, claims)
        drafts.append(draft)

    ctx.session.state["app:drafts"] = drafts
    return {"sections_drafted": len(drafts), "message": f"Drafted {len(drafts)} sections"}


async def render_output(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Render final report from drafts."""
    logger.info("render_output: assembling final report")
    drafts = ctx.session.state.get("app:drafts", [])
    objective = ctx.session.state.get("app:objective", {})
    claims = ctx.session.state.get("app:claims", [])

    # Build a simple markdown report
    title = objective.get("title", "Research Report")
    lines = [f"# {title}\n"]

    for d in drafts:
        content = d.get("content", "")
        if content:
            lines.append(content)
            lines.append("")

    # Add evidence summary
    lines.append("## Sources & Evidence")
    lines.append(f"- Total claims: {len(claims)}")
    lines.append(f"- Sections drafted: {len(drafts)}")

    report = "\n".join(lines)
    ctx.session.state["app:final_report"] = report
    return {"output_format": "markdown", "report_length": len(report), "message": "Pipeline complete — report generated"}


# ── Remaining stub nodes (to be implemented in later phases) ──────────────

async def approve_plan(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"approved": True, "message": "Plan auto-approved"}

async def scheduler_select(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"next_question_id": None, "message": "Scheduler stub"}

async def source_policy_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"accepted": len(ctx.session.state.get("app:sources", [])), "rejected": 0, "message": "All sources accepted"}

async def contradictions_search(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"contradictions_found": 0, "message": "Contradiction search stub"}

async def coverage_calculate(ctx: Context, node_input: Any) -> dict[str, Any]:
    claims = ctx.session.state.get("app:claims", [])
    return {"primary_source_coverage": 0.5, "information_gain": 0.1, "claims_count": len(claims)}

async def stop_evaluate(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"should_stop": True, "reason": "Phase 1: single-pass pipeline"}

async def approve_outline(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"approved": True, "message": "Outline auto-approved"}

async def verify_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"blocking_findings": 0, "passed": True, "message": "Verification stub"}

async def repair_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"issues_repaired": 0, "message": "Repair stub"}

async def final_gate_check(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"approved": True, "message": "Final gate auto-approved"}


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
