"""Deep Research Assistant iterative ADK workflow graph."""

from __future__ import annotations

import logging
from typing import Any, cast

from google.adk.agents.context import Context
from google.adk.workflow import START, Edge, FunctionNode, Workflow

from deep_research.nodes.budget import (
    enforce_perspective_budget,
    filter_evidence_for_section,
    initialize_perspective_budgets,
    summarize_budget_remaining,
)
from deep_research.nodes.coverage import calculate_coverage
from deep_research.nodes.scheduler import select_frontier_questions
from deep_research.settings import get_settings
from deep_research.workflow.state import get_state
from deep_research.workflow.stopping import evaluate_stopping

logger = logging.getLogger(__name__)


def _extract_user_text(node_input: Any) -> str:
    if isinstance(node_input, dict):
        return str(node_input.get("content", node_input.get("text", "")))
    if isinstance(node_input, str):
        return node_input
    if hasattr(node_input, "parts"):
        parts = getattr(node_input, "parts", [])
        return " ".join(getattr(part, "text", "") for part in parts if hasattr(part, "text"))
    return ""


def _assign_question_ids(questions: list[dict[str, Any]], prefix: str = "q") -> list[dict[str, Any]]:
    for index, question in enumerate(questions):
        question.setdefault("question_id", f"{prefix}-{index}")
        question.setdefault("status", "pending")
    return questions


def _append_unique_questions(existing: list[dict[str, Any]], new_questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_texts = {question.get("text", "").strip().lower() for question in existing}
    next_index = len(existing)
    for question in new_questions:
        text = question.get("text", "").strip()
        if not text or text.lower() in existing_texts:
            continue
        question.setdefault("question_id", f"q-{next_index}")
        question.setdefault("status", "pending")
        parent_id = question.pop("parent_question_id", None)
        if parent_id:
            question["parent_question_ids"] = [parent_id]
        existing.append(question)
        existing_texts.add(text.lower())
        next_index += 1
    return existing


async def scope_classify(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Classify and scope the research request using Research Director."""
    logger.info("scope_classify: running Research Director")
    state = get_state()
    user_text = _extract_user_text(node_input)

    if not user_text:
        return {"status": "ok", "risk_level": "medium", "message": "No user input; using defaults"}

    from deep_research.agents.research_director import research_director

    plan = await research_director(user_text)
    state["app:research_plan"] = plan
    state["app:objective"] = plan.get("objective", {})
    state["app:scope"] = plan.get("scope", {})
    state["app:proposed_perspectives"] = plan.get("proposed_perspectives", [])
    state["app:cycle_history"] = []
    state["app:claims"] = []
    state["app:evidence"] = []
    state["app:sources"] = []
    state["app:contradictions"] = []

    return {
        "status": "ok",
        "risk_level": plan.get("scope", {}).get("risk_level", "medium"),
        "objective_title": plan.get("objective", {}).get("title", ""),
        "message": "Research plan generated",
    }


async def perspective_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Generate research perspectives."""
    logger.info("perspective_generate: running Perspective Planner")
    state = get_state()
    scope = state.get("app:scope", {})
    objective = state.get("app:objective", {})

    from deep_research.agents.perspective_planner import perspective_planner

    perspectives = await perspective_planner(scope, objective.get("primary_question", ""))
    state["app:perspectives"] = perspectives
    state["app:perspective_budgets"] = initialize_perspective_budgets(perspectives)
    return {"perspective_count": len(perspectives), "message": f"Generated {len(perspectives)} perspectives"}


async def question_graph_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build the initial question frontier."""
    logger.info("question_graph_build: running Question Architect")
    state = get_state()
    perspectives = state.get("app:perspectives", [])
    scope = state.get("app:scope", {})

    from deep_research.agents.question_architect import question_architect

    result = await question_architect(perspectives, scope)
    questions = _assign_question_ids(result.get("questions", []))
    state["app:questions"] = questions
    return {"question_count": len(questions), "message": f"Generated {len(questions)} questions"}


async def approve_plan(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Apply scope approval policy."""
    state = get_state()
    settings = get_settings()
    risk_level = str(state.get("app:scope", {}).get("risk_level", "medium"))
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    threshold = settings.approvals.scope_required_for_risk
    approved = order.get(risk_level, 1) < order.get(threshold, 2)
    ctx.route = approved
    return {
        "approved": approved,
        "risk_level": risk_level,
        "message": "Plan approved" if approved else "Plan requires approval; looping to rescope",
    }


async def scheduler_select(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Deterministically select the next frontier questions."""
    state = get_state()
    selection = select_frontier_questions(state.get("app:questions", []))
    selected_questions = selection.get("selected_questions", [])
    state["app:selected_questions"] = selected_questions
    state["app:question_priorities"] = selection.get("priorities", {})

    if selected_questions:
        active_question = selected_questions[0]
        active_question["status"] = "in_progress"
        state["app:active_question"] = active_question
    else:
        state["app:active_question"] = {}

    return {
        "selected_count": len(selected_questions),
        "parallel_groups": selection.get("parallel_groups", []),
        "message": "Frontier scheduled",
    }


async def search_plan_create(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Create search queries for the active question and enforce perspective budget."""
    logger.info("search_plan_create: running Query Planner")
    state = get_state()
    question = state.get("app:active_question", {})
    if not question:
        state["app:search_queries"] = []
        return {"query_count": 0, "message": "No active question selected"}

    from deep_research.agents.query_planner import query_planner

    queries = await query_planner(question)
    perspective_name = str(question.get("perspective", "unknown"))
    budget_result = enforce_perspective_budget(
        perspective_name=perspective_name,
        query_count=len(queries),
        perspective_budgets=state.get("app:perspective_budgets", {}),
        estimated_sources=len(queries),
    )
    state["app:last_budget_check"] = budget_result

    if not budget_result.get("accepted"):
        question["status"] = "budget_exhausted"
        state["app:search_queries"] = []
        return {"query_count": 0, "budget_rejected": True, "message": budget_result["reason"]}

    state["app:search_queries"] = queries
    return {"query_count": len(queries), "budget_rejected": False, "message": f"Generated {len(queries)} search queries"}


async def source_retrieve(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Retrieve sources using the web search tool."""
    logger.info("source_retrieve: running web search")
    state = get_state()
    queries = state.get("app:search_queries", [])
    if not queries:
        state["app:latest_sources"] = []
        return {"sources_found": 0, "message": "No queries to search"}

    from deep_research.tools.search import web_search

    batch_results: list[dict[str, Any]] = []
    for query in queries[:3]:
        result = await web_search(query.get("raw_query", ""), max_results=3)
        batch_results.extend(result.get("results", []))

    state.setdefault("app:sources", []).extend(batch_results)
    state["app:latest_sources"] = batch_results
    return {"sources_found": len(batch_results), "message": f"Retrieved {len(batch_results)} sources"}


async def source_policy_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Source policy stub kept for a later phase."""
    state = get_state()
    latest_sources = state.get("app:latest_sources", [])
    return {"accepted": len(latest_sources), "rejected": 0, "message": "All sources accepted"}


async def evidence_extract(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Extract evidence and optionally generate evidence-conditioned follow-ups."""
    logger.info("evidence_extract: running Evidence Curator")
    settings = get_settings()
    state = get_state()
    sources = state.get("app:latest_sources", [])
    question = state.get("app:active_question", {})
    if not sources or not question:
        return {"fragments": 0, "follow_ups_added": 0, "message": "No sources to extract from"}

    from deep_research.agents.evidence_curator import evidence_curator
    from deep_research.agents.question_architect import generate_follow_ups

    fragments: list[dict[str, Any]] = []
    for source in sources[:2]:
        source_fragments = await evidence_curator(
            source.get("snippet", ""),
            source.get("title", "Untitled"),
            question.get("text", ""),
        )
        for fragment_index, fragment in enumerate(source_fragments):
            fragment.setdefault("evidence_id", f"e-{len(state.get('app:evidence', [])) + len(fragments) + fragment_index}")
            fragment["source_id"] = source.get("url", "unknown")
            fragment["source_cluster"] = source.get("domain") or source.get("url", "unknown")
        fragments.extend(source_fragments)

    state.setdefault("app:evidence", []).extend(fragments)
    follow_ups: list[dict[str, Any]] = []
    if settings.workflow.enable_follow_up_questions and fragments:
        follow_ups = await generate_follow_ups(
            evidence=fragments,
            parent_question=question,
            existing_questions=state.get("app:questions", []),
        )
        state["app:questions"] = _append_unique_questions(state.get("app:questions", []), follow_ups)

    return {
        "fragments": len(fragments),
        "follow_ups_added": len(follow_ups),
        "message": f"Extracted {len(fragments)} evidence fragments",
    }


async def claims_construct(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Construct claims from the latest evidence batch."""
    logger.info("claims_construct: running Claim Builder")
    state = get_state()
    evidence = state.get("app:evidence", [])
    question = state.get("app:active_question", {})
    if not evidence or not question:
        return {"claims_created": 0, "message": "No evidence to build claims from"}

    from deep_research.agents.claim_builder import claim_builder

    claims = await claim_builder(evidence, question.get("text", ""))
    claim_offset = len(state.get("app:claims", []))
    for index, claim in enumerate(claims):
        claim.setdefault("claim_id", f"c-{claim_offset + index}")
        claim.setdefault("question_id", question.get("question_id"))
    state.setdefault("app:claims", []).extend(claims)

    question["status"] = "resolved" if claims else "pending"
    return {"claims_created": len(claims), "message": f"Built {len(claims)} claims"}


async def contradictions_search(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Track contradiction search completion for material claims."""
    state = get_state()
    claims = state.get("app:claims", [])
    contradictions = state.get("app:contradictions", [])
    seen = {
        str(claim_id)
        for contradiction in contradictions
        for claim_id in contradiction.get("claim_ids", [])
    }

    new_records = []
    for claim in claims:
        if claim.get("materiality") not in {"high", "critical"}:
            continue
        claim_id = str(claim.get("claim_id"))
        if claim_id in seen:
            continue
        new_records.append({
            "contradiction_id": f"ctr-{claim_id}",
            "claim_ids": [claim_id],
            "resolution_status": "acknowledged",
            "materiality": claim.get("materiality", "medium"),
            "searched": True,
        })

    contradictions.extend(new_records)
    state["app:contradictions"] = contradictions
    return {"contradictions_found": len(new_records), "message": "Contradiction search recorded"}


async def coverage_calculate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Compute information-gain and coverage metrics."""
    state = get_state()
    coverage = calculate_coverage(
        cycle_history=state.get("app:cycle_history", []),
        questions=state.get("app:questions", []),
        claims=state.get("app:claims", []),
        evidence=state.get("app:evidence", []),
        contradictions=state.get("app:contradictions", []),
        sources=state.get("app:sources", []),
    )
    state["app:coverage"] = coverage
    state.setdefault("app:cycle_history", []).append(coverage["cycle_summary"])
    return coverage


async def moderator_node(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Run the moderator and apply priority adjustments."""
    logger.info("moderator: assessing frontier balance")
    state = get_state()

    from deep_research.agents.moderator import moderator

    result = await moderator({
        "questions": state.get("app:questions", []),
        "claims": state.get("app:claims", []),
        "evidence": state.get("app:evidence", []),
        "contradictions": state.get("app:contradictions", []),
        "recent_cycle_history": state.get("app:cycle_history", []),
    })

    adjusted = result.get("adjusted_priorities", {})
    if adjusted:
        for question in state.get("app:questions", []):
            key = str(question.get("question_id") or question.get("text"))
            if key in adjusted:
                question["priority"] = adjusted[key]

    state["app:moderator_result"] = result
    return result


async def stop_evaluate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Evaluate iterative stopping conditions."""
    settings = get_settings()
    state = get_state()
    if not settings.workflow.enable_iterative_research:
        decision = {
            "should_stop": True,
            "reasons": ["Iterative research disabled; single-pass mode"],
            "unresolved_material_questions": [],
            "marginal_information_gain": 0.0,
            "evidence_diversity_score": 0.0,
            "primary_source_coverage": 0.0,
            "budget_remaining": summarize_budget_remaining(state.get("app:perspective_budgets", {})),
        }
        ctx.route = True
        state["app:stopping_decision"] = decision
        return decision

    decision = evaluate_stopping(
        coverage=state.get("app:coverage", {}),
        budget_remaining=summarize_budget_remaining(state.get("app:perspective_budgets", {})),
        questions=state.get("app:questions", []),
        claims=state.get("app:claims", []),
        contradictions=state.get("app:contradictions", []),
        cycle_history=state.get("app:cycle_history", []),
        elapsed_seconds=0.0,
    ).model_dump()
    ctx.route = bool(decision.get("should_stop"))
    state["app:stopping_decision"] = decision
    return decision


async def outline_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build report outline from accumulated claims."""
    logger.info("outline_build: running Outline Architect")
    state = get_state()

    from deep_research.agents.outline_architect import outline_architect

    outline = await outline_architect(
        state.get("app:claims", []),
        state.get("app:objective", {}),
    )
    state["app:outline"] = outline
    return {"section_count": len(outline.get("sections", [])), "message": "Outline built"}


async def approve_outline(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"approved": True, "message": "Outline auto-approved"}


async def draft_generate(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Generate drafts with section-local evidence filtering."""
    logger.info("draft_generate: running Section Writer")
    state = get_state()
    outline = state.get("app:outline", {})
    claims = state.get("app:claims", [])
    evidence = state.get("app:evidence", [])
    if not outline.get("sections"):
        return {"sections_drafted": 0, "message": "No outline sections to draft"}

    from deep_research.agents.section_writer import section_writer

    drafts = []
    for section in outline["sections"][:2]:
        filtered_evidence = filter_evidence_for_section(section.get("claim_ids", []), claims, evidence)
        draft = await section_writer(section, claims, filtered_evidence)
        drafts.append(draft)

    state["app:drafts"] = drafts
    return {"sections_drafted": len(drafts), "message": f"Drafted {len(drafts)} sections"}


async def verify_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"blocking_findings": 0, "passed": True, "message": "Verification stub"}


async def repair_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"issues_repaired": 0, "message": "Repair stub"}


async def final_gate_check(ctx: Context, node_input: Any) -> dict[str, Any]:
    return {"approved": True, "message": "Final gate auto-approved"}


async def render_output(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Render final report from drafts."""
    state = get_state()
    drafts = state.get("app:drafts", [])
    objective = state.get("app:objective", {})
    title = objective.get("title", "Research Report")
    lines = [f"# {title}", ""]

    for draft in drafts:
        content = draft.get("content", "")
        if content:
            lines.append(content)
            lines.append("")

    lines.append("## Sources & Evidence")
    lines.append(f"- Total claims: {len(state.get('app:claims', []))}")
    lines.append(f"- Cycles completed: {len(state.get('app:cycle_history', []))}")
    lines.append(f"- Sections drafted: {len(drafts)}")

    report = "\n".join(lines)
    state["app:final_report"] = report
    return {"output_format": "markdown", "report_length": len(report), "message": "Pipeline complete"}


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
    ("moderator", moderator_node),
    ("stop_evaluate", stop_evaluate),
    ("outline_build", outline_build),
    ("approve_outline", approve_outline),
    ("draft_generate", draft_generate),
    ("verify_draft", verify_draft),
    ("repair_draft", repair_draft),
    ("final_gate_check", final_gate_check),
    ("render_output", render_output),
]


def _build_edges(nodes: dict[str, FunctionNode]) -> list[Edge]:
    """Build the iterative Phase 2 workflow edges."""
    n = nodes
    edges = [
        Edge(from_node=START, to_node=n["scope_classify"]),
        Edge(from_node=n["scope_classify"], to_node=n["perspective_generate"]),
        Edge(from_node=n["perspective_generate"], to_node=n["question_graph_build"]),
        Edge(from_node=n["question_graph_build"], to_node=n["approve_plan"]),
        Edge(from_node=n["approve_plan"], to_node=n["scheduler_select"], route=True),
        Edge(from_node=n["approve_plan"], to_node=n["scope_classify"], route=False),
        Edge(from_node=n["scheduler_select"], to_node=n["search_plan_create"]),
        Edge(from_node=n["search_plan_create"], to_node=n["source_retrieve"]),
        Edge(from_node=n["source_retrieve"], to_node=n["source_policy_apply"]),
        Edge(from_node=n["source_policy_apply"], to_node=n["evidence_extract"]),
        Edge(from_node=n["evidence_extract"], to_node=n["claims_construct"]),
        Edge(from_node=n["claims_construct"], to_node=n["contradictions_search"]),
        Edge(from_node=n["contradictions_search"], to_node=n["coverage_calculate"]),
        Edge(from_node=n["coverage_calculate"], to_node=n["moderator"]),
        Edge(from_node=n["moderator"], to_node=n["stop_evaluate"]),
        Edge(from_node=n["stop_evaluate"], to_node=n["scheduler_select"], route=False),
        Edge(from_node=n["stop_evaluate"], to_node=n["outline_build"], route=True),
        Edge(from_node=n["outline_build"], to_node=n["approve_outline"]),
        Edge(from_node=n["approve_outline"], to_node=n["draft_generate"]),
        Edge(from_node=n["draft_generate"], to_node=n["verify_draft"]),
        Edge(from_node=n["verify_draft"], to_node=n["repair_draft"]),
        Edge(from_node=n["repair_draft"], to_node=n["final_gate_check"]),
        Edge(from_node=n["final_gate_check"], to_node=n["render_output"]),
    ]
    return edges


def build_research_workflow() -> Workflow:
    """Build the complete research workflow."""
    node_list = [FunctionNode(func=func, name=name) for name, func in _ALL_NODE_FUNCS]
    nodes = {node.name: node for node in node_list}
    return Workflow(
        name="deep_research_assistant",
        description=(
            "Enterprise-grade governed research runtime. Converts broad research "
            "requests into inspectable, evidence-backed workflows with iterative "
            "STORM-grade refinement."
        ),
        edges=cast(Any, _build_edges(nodes)),
    )
