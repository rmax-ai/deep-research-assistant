"""Deep Research Assistant collaborative ADK workflow graph."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from google.adk.agents.context import Context
from google.adk.workflow import START, Edge, FunctionNode, Workflow

from deep_research.nodes.approval import ApprovalGate, check_gate
from deep_research.nodes.budget import (
    enforce_perspective_budget,
    filter_evidence_for_section,
    initialize_perspective_budgets,
    summarize_budget_remaining,
)
from deep_research.nodes.coverage import calculate_coverage
from deep_research.nodes.deduplication import cluster_sources, deduplicate_sources
from deep_research.nodes.scheduler import select_frontier_questions
from deep_research.nodes.scope import apply_scope_change
from deep_research.policies.engine import evaluate_policy
from deep_research.policies.identity import get_current_principal
from deep_research.settings import get_settings
from deep_research.telemetry.events import get_event_bus
from deep_research.workflow.state import get_state
from deep_research.workflow.stopping import evaluate_stopping

logger = logging.getLogger(__name__)


def _workflow_log(level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra=fields)


def _question_context(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": str(question.get("question_id", "")) or None,
        "perspective": str(question.get("perspective", "")) or None,
    }


def _node_context(state: dict[str, Any], node: str) -> dict[str, Any]:
    active_question = state.get("app:active_question", {})
    return {
        "run_id": _run_id(state) or None,
        "phase": str(state.get("app:phase", "")) or None,
        "node": node,
        **_question_context(active_question if isinstance(active_question, dict) else {}),
    }


def _result_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"result_type": type(result).__name__}

    summary: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, (bool, int, float)) or value is None:
            summary[key] = value
            continue
        if isinstance(value, str):
            summary[key] = value if len(value) <= 160 else f"{value[:157]}..."
            continue
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
            continue
        if isinstance(value, dict):
            if "status" in value and isinstance(value["status"], str):
                summary[f"{key}_status"] = value["status"]
            else:
                summary[f"{key}_count"] = len(value)
    return summary


def _state_counts(state: dict[str, Any]) -> dict[str, int]:
    return {
        "questions": len(state.get("app:questions", [])),
        "claims": len(state.get("app:claims", [])),
        "evidence": len(state.get("app:evidence", [])),
        "sources": len(state.get("app:sources", [])),
        "contradictions": len(state.get("app:contradictions", [])),
        "drafts": len(state.get("app:drafts", [])),
        "cycles": len(state.get("app:cycle_history", [])),
    }


async def _publish_route_selection(state: dict[str, Any], node: str, route: int) -> None:
    await _publish(
        "route.selected",
        run_id=_run_id(state),
        node=node,
        route=route,
        phase=state.get("app:phase", ""),
        message=f"{node} selected route {route}",
    )


def _instrument_node(node_name: str, node_func: Any) -> Any:
    async def _wrapped(ctx: Context, node_input: Any) -> dict[str, Any]:
        state = get_state()
        start_context = _node_context(state, node_name)
        await _publish(
            "node.started",
            **start_context,
            counts=_state_counts(state),
            message=f"{node_name} started",
        )
        _workflow_log(logging.DEBUG, "workflow node started", status="started", **start_context)
        started_at = time.perf_counter()

        try:
            result = await node_func(ctx, node_input)
        except Exception as exc:
            state = get_state()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            failure_context = _node_context(state, node_name)
            await _publish(
                "node.failed",
                **failure_context,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                counts=_state_counts(state),
                message=f"{node_name} failed",
            )
            _workflow_log(
                logging.ERROR,
                "workflow node failed",
                status="failed",
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                counts=_state_counts(state),
                **failure_context,
            )
            raise

        state = get_state()
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        route = getattr(ctx, "route", None)
        completion_context = _node_context(state, node_name)
        await _publish(
            "node.completed",
            **completion_context,
            status="ok",
            duration_ms=duration_ms,
            route=route,
            result=_result_summary(result),
            counts=_state_counts(state),
            message=f"{node_name} completed",
        )
        _workflow_log(
            logging.DEBUG,
            "workflow node completed",
            status="ok",
            duration_ms=duration_ms,
            route=route,
            result=_result_summary(result),
            counts=_state_counts(state),
            **completion_context,
        )
        if isinstance(route, int):
            await _publish_route_selection(state, node_name, route)
            _workflow_log(
                logging.DEBUG,
                "workflow route selected",
                route=route,
                **completion_context,
            )
        return cast(dict[str, Any], result)

    return _wrapped


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


async def _publish(event_type: str, **payload: Any) -> None:
    run_id = str(payload.get("run_id", ""))
    await get_event_bus().publish(event_type, {"run_id": run_id, **payload})


def _run_id(state: dict[str, Any]) -> str:
    return str(state.get("app:run_id", ""))


def _approval_input_for(run_state: dict[str, Any], gate: str) -> str | None:
    entry = run_state.get("app:approval_inputs", {}).get(gate)
    if isinstance(entry, dict):
        return entry.get("status")
    if isinstance(entry, str):
        return entry
    decision = run_state.get("app:approval_decisions", {}).get(gate, {})
    status = decision.get("status")
    return status if isinstance(status, str) else None


async def _resolve_approval(ctx: Context, gate: ApprovalGate, state: dict[str, Any]) -> dict[str, Any]:
    if not gate.required:
        ctx.route = 2
        gate.status = "not_required"
    else:
        status = _approval_input_for(state, gate.gate) or "approved"
        gate.status = status
        if status == "rejected":
            ctx.route = 0
        else:
            ctx.route = 1
        await _publish(
            "approval.requested",
            run_id=_run_id(state),
            gate=gate.gate,
            required=True,
            status=gate.status,
            display_data=gate.display_data,
            approval_gate=gate.gate,
            message=f"Approval gate {gate.gate} is {gate.status}",
        )

    decisions = state.setdefault("app:approval_decisions", {})
    decisions[gate.gate] = gate.model_dump()
    return gate.model_dump()


async def scope_classify(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Classify and scope the research request using Research Director."""
    logger.info("scope_classify: running Research Director")
    state = get_state()
    user_text = _extract_user_text(node_input)
    run_id = _run_id(state)

    if not state.get("app:run_started_emitted"):
        await _publish("run.started", run_id=run_id, message="Research run started")
        state["app:run_started_emitted"] = True

    if not user_text:
        return {"status": "ok", "risk_level": "medium", "message": "No user input; using defaults"}

    from deep_research.agents.research_director import research_director

    plan = await research_director(user_text)
    state["app:research_plan"] = plan
    state["app:objective"] = plan.get("objective", {})
    state["app:scope"] = plan.get("scope", {})
    state["app:proposed_perspectives"] = plan.get("proposed_perspectives", [])
    state.setdefault("app:cycle_history", [])
    state.setdefault("app:claims", [])
    state.setdefault("app:evidence", [])
    state.setdefault("app:sources", [])
    state.setdefault("app:contradictions", [])
    state.setdefault("app:approval_decisions", {})
    state.setdefault("app:pending_interventions", [])
    state.setdefault("app:pending_scope_changes", [])

    await _publish(
        "scope.proposed",
        run_id=run_id,
        objective=state["app:objective"],
        scope=state["app:scope"],
        message="Scope proposed",
    )
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
    await _publish(
        "perspective.created",
        run_id=_run_id(state),
        perspectives=perspectives,
        perspective_count=len(perspectives),
        message=f"Generated {len(perspectives)} perspectives",
    )
    return {"perspective_count": len(perspectives), "message": f"Generated {len(perspectives)} perspectives"}


async def question_graph_build(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Build or refresh the question frontier."""
    logger.info("question_graph_build: running Question Architect")
    state = get_state()
    perspectives = state.get("app:perspectives", [])
    scope = state.get("app:scope", {})

    from deep_research.agents.question_architect import question_architect

    result = await question_architect(perspectives, scope)
    new_questions = _assign_question_ids(result.get("questions", []))
    if state.get("app:questions") and state.get("app:scope_replan_required"):
        state["app:questions"] = _append_unique_questions(state.get("app:questions", []), new_questions)
        state["app:scope_replan_required"] = False
    else:
        state["app:questions"] = new_questions
    state["app:questions_version"] = int(state.get("app:questions_version", 0)) + 1

    await _publish(
        "question.created",
        run_id=_run_id(state),
        questions=state["app:questions"],
        version=state["app:questions_version"],
        question_count=len(state["app:questions"]),
        message=f"Question graph version {state['app:questions_version']}",
    )
    return {
        "question_count": len(state["app:questions"]),
        "message": f"Generated {len(state['app:questions'])} questions",
    }


async def approve_plan(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Apply scope and plan approval policy."""
    state = get_state()
    settings = get_settings()

    gate_a = await check_gate("A", state, settings)
    state["app:last_gate_A"] = gate_a.model_dump()
    if gate_a.required:
        gate_a.status = _approval_input_for(state, "A") or "approved"
        state.setdefault("app:approval_decisions", {})["A"] = gate_a.model_dump()
        await _publish(
            "approval.requested",
            run_id=_run_id(state),
            gate=gate_a.gate,
            required=True,
            status=gate_a.status,
            display_data=gate_a.display_data,
        )
        if gate_a.status == "rejected":
            ctx.route = 0
            return gate_a.model_dump()

    gate_b = await check_gate("B", state, settings)
    state["app:last_gate_B"] = gate_b.model_dump()
    return await _resolve_approval(ctx, gate_b if gate_b.required else gate_a if gate_a.required else gate_b, state)


async def scheduler_select(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Deterministically select the next frontier questions."""
    state = get_state()
    selection = select_frontier_questions(state.get("app:questions", []))
    selected_questions = selection.get("selected_questions", [])
    state["app:scheduler_result"] = selection
    state["app:selected_questions"] = selected_questions
    state["app:question_priorities"] = selection.get("priorities", {})

    if selected_questions:
        active_question = selected_questions[0]
        active_question["status"] = "in_progress"
        state["app:active_question"] = active_question
        state["app:phase"] = "researching"
    else:
        state["app:active_question"] = {}

    return {
        "selected_count": len(selected_questions),
        "parallel_groups": selection.get("parallel_groups", []),
        "message": "Frontier scheduled",
    }


async def plan_not_required(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Bridge node for plan gates that are not required."""
    return {"message": "Plan approval not required"}


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
    await _publish(
        "budget.checked",
        run_id=_run_id(state),
        node="search_plan_create",
        perspective=perspective_name,
        accepted=bool(budget_result.get("accepted")),
        query_count=len(queries),
        reason=budget_result.get("reason", ""),
        message=f"Budget {'accepted' if budget_result.get('accepted') else 'rejected'} for {perspective_name}",
    )

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
        await _publish(
            "query.executed",
            run_id=_run_id(state),
            query=query,
            results_count=len(result.get("results", [])),
            message=f"Executed query {query.get('raw_query', '')[:80]}",
        )

    state.setdefault("app:sources", []).extend(batch_results)
    state["app:latest_sources"] = batch_results
    return {"sources_found": len(batch_results), "message": f"Retrieved {len(batch_results)} sources"}


async def source_policy_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Real source policy: classify, filter, and deduplicate sources."""
    state = get_state()
    sources = state.get("app:latest_sources", [])

    if not sources:
        return {"accepted": 0, "rejected": 0, "message": "No sources to filter"}

    principal = get_current_principal(state)

    # Deduplicate by URL/title
    unique = deduplicate_sources(sources)
    deduped_count = len(sources) - len(unique)
    sources = unique

    # Classify and filter
    accepted = []
    rejected = []
    for src in sources:
        # Check policy for source retrieval
        decision = evaluate_policy(
            dict(principal),
            action="source_retrieve",
            resource=str(src.get("canonical_uri", src.get("url", ""))),
            context={"stage": state.get("app:phase", "")},
        )
        if decision.value == "deny":
            rejected.append({**src, "rejection_reason": "policy_deny"})
            continue

        # Simple heuristics for source quality
        url = str(src.get("canonical_uri", src.get("url", "")))
        # Apply source constraints from scope
        scope = state.get("app:scope", {})
        source_constraints = scope.get("source_constraints", {})
        blocked = source_constraints.get("blocked_domains", [])
        if any(d in url for d in blocked):
            rejected.append({**src, "rejection_reason": "blocked_domain"})
            continue

        src["policy_status"] = "accepted"
        accepted.append(src)

    # Assign independence clusters
    accepted = cluster_sources(accepted)

    state["app:sources"] = list(state.get("app:sources", [])) + accepted
    state["app:rejected_sources"] = rejected

    await _publish(
        "source.accepted",
        run_id=_run_id(state),
        sources=accepted,
        accepted=len(accepted),
        rejected=len(rejected),
        deduplicated=deduped_count,
        message=f"Accepted {len(accepted)} sources",
    )
    await _publish(
        "policy.applied",
        run_id=_run_id(state),
        node="source_policy_apply",
        accepted=len(accepted),
        rejected=len(rejected),
        deduplicated=deduped_count,
        message="Applied source policy filters",
    )

    return {
        "accepted": len(accepted),
        "rejected": len(rejected) + deduped_count,
        "deduplicated": deduped_count,
        "message": f"Accepted {len(accepted)}, rejected {len(rejected)}, deduplicated {deduped_count}",
    }


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
            fragment["question_id"] = question.get("question_id")
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

    await _publish(
        "evidence.extracted",
        run_id=_run_id(state),
        evidence=fragments,
        follow_ups_added=len(follow_ups),
        fragments_count=len(fragments),
        question_id=question.get("question_id"),
        message=f"Extracted {len(fragments)} evidence fragments",
    )
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

    await _publish(
        "claim.created",
        run_id=_run_id(state),
        claims=claims,
        claim_count=len(claims),
        question_id=question.get("question_id"),
        message=f"Built {len(claims)} claims",
    )
    return {"claims_created": len(claims), "message": f"Built {len(claims)} claims"}


async def knowledge_organize(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Project questions, claims, and evidence into a topic graph."""
    state = get_state()

    from deep_research.agents.knowledge_organizer import knowledge_organizer

    concept_map = await knowledge_organizer(
        state.get("app:questions", []),
        state.get("app:claims", []),
        state.get("app:evidence", []),
    )
    state["app:concept_map"] = concept_map
    return {
        "topic_nodes": len(concept_map.get("topic_nodes", [])),
        "edges": len(concept_map.get("edges", [])),
        "message": "Knowledge graph updated",
    }


async def contradictions_search(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Run counter-evidence agent and detect contradictions between claims."""
    state = get_state()
    claims = state.get("app:claims", [])
    evidence = state.get("app:evidence", [])
    sources = state.get("app:sources", [])

    if not claims:
        return {"contradictions_found": 0, "message": "No claims to check for contradictions"}

    # 1. Run counter-evidence agent (LLM-backed)
    from deep_research.agents.counter_evidence import counter_evidence_agent
    counter_result = await counter_evidence_agent(claims, evidence, sources)

    # 2. Deterministic contradiction detection between claims
    from deep_research.nodes.contradictions import detect_contradictions
    detected = detect_contradictions(claims, evidence)

    # Merge with existing contradictions
    existing = state.get("app:contradictions", [])
    existing_ids = {c.get("contradiction_id") for c in existing}
    new_contradictions = [c for c in detected if c.get("contradiction_id") not in existing_ids]

    contradictions = existing + new_contradictions
    state["app:contradictions"] = contradictions
    state["app:counter_evidence"] = counter_result

    if new_contradictions:
        await _publish(
            "contradiction.detected",
            run_id=_run_id(state),
            contradictions=new_contradictions,
            contradiction_count=len(new_contradictions),
            message=f"Detected {len(new_contradictions)} contradictions",
        )

    return {
        "contradictions_found": len(new_contradictions),
        "counter_evidence_issues": len(counter_result.get("independence_issues", [])),
        "total_contradictions": len(contradictions),
        "message": f"Found {len(new_contradictions)} new contradictions",
    }


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
    await _publish(
        "coverage.updated",
        run_id=_run_id(state),
        coverage=coverage,
        marginal_information_gain=coverage.get("marginal_information_gain", 0.0),
        primary_source_coverage=coverage.get("primary_source_coverage", 0.0),
        evidence_diversity_score=coverage.get("evidence_diversity_score", 0.0),
        message="Coverage metrics updated",
    )
    return coverage


async def moderator_node(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Run the moderator and apply priority adjustments."""
    logger.info("moderator: assessing frontier balance")
    state = get_state()

    from deep_research.agents.moderator import moderator

    result = await moderator(
        {
            "questions": state.get("app:questions", []),
            "claims": state.get("app:claims", []),
            "evidence": state.get("app:evidence", []),
            "contradictions": state.get("app:contradictions", []),
            "recent_cycle_history": state.get("app:cycle_history", []),
        }
    )

    adjusted = result.get("adjusted_priorities", {})
    if adjusted:
        for question in state.get("app:questions", []):
            key = str(question.get("question_id") or question.get("text"))
            if key in adjusted:
                question["priority"] = adjusted[key]

    state["app:moderator_result"] = result
    return result


async def interventions_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Apply queued user interventions."""
    state = get_state()
    pending = list(state.get("app:pending_interventions", []))
    if not pending:
        return {"applied": 0, "scope_changes": 0, "message": "No interventions queued"}

    state["app:pending_interventions"] = []
    scope_changes = 0
    applied = 0
    for intervention in pending:
        intervention_type = str(intervention.get("type", ""))
        if intervention_type in {"add_topic", "remove_topic", "add_perspective", "change_budget"}:
            state.setdefault("app:pending_scope_changes", []).append(intervention)
            scope_changes += 1
            applied += 1
            continue
        if intervention_type == "add_question":
            next_index = len(state.get("app:questions", []))
            state.setdefault("app:questions", []).append(
                {
                    "question_id": f"q-user-{next_index}",
                    "text": intervention.get("instruction", ""),
                    "priority": 1.0,
                    "perspective": "user_requested",
                    "status": "pending",
                }
            )
            applied += 1
            continue
        if intervention_type == "challenge_claim":
            target_id = intervention.get("target_id")
            state.setdefault("app:contradictions", []).append(
                {
                    "contradiction_id": f"ctr-user-{target_id or applied}",
                    "claim_ids": [target_id] if target_id else [],
                    "resolution_status": "challenged",
                    "materiality": "high",
                    "searched": False,
                    "instruction": intervention.get("instruction", ""),
                }
            )
            applied += 1

    return {"applied": applied, "scope_changes": scope_changes, "message": "Interventions applied"}


async def scope_change_apply(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Apply queued scope changes and trigger question-graph re-evaluation."""
    state = get_state()
    pending_changes = list(state.get("app:pending_scope_changes", []))
    if not pending_changes:
        ctx.route = 0
        return {"applied": 0, "message": "No scope changes queued"}

    state["app:pending_scope_changes"] = []
    updated = state
    for change in pending_changes:
        updated = await apply_scope_change(updated, change)

    state.clear()
    state.update(updated)
    ctx.route = 1
    return {"applied": len(pending_changes), "message": "Scope changed; rebuilding question graph"}


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
        ctx.route = 1
        state["app:stopping_decision"] = decision
        state["app:stop_result"] = decision
        await _publish(
            "stop.evaluated",
            run_id=_run_id(state),
            should_stop=True,
            stop_reasons=decision["reasons"],
            unresolved_material_questions=0,
            message="Stop evaluation completed",
        )
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
    ctx.route = 1 if bool(decision.get("should_stop")) else 0
    state["app:stopping_decision"] = decision
    state["app:stop_result"] = decision
    await _publish(
        "stop.evaluated",
        run_id=_run_id(state),
        should_stop=bool(decision.get("should_stop")),
        stop_reasons=decision.get("reasons", []),
        unresolved_material_questions=len(decision.get("unresolved_material_questions", [])),
        marginal_information_gain=decision.get("marginal_information_gain", 0.0),
        primary_source_coverage=decision.get("primary_source_coverage", 0.0),
        message="Stop evaluation completed",
    )
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
    await _publish("outline.proposed", run_id=_run_id(state), outline=outline)
    _workflow_log(
        logging.INFO,
        "workflow outline proposed",
        run_id=_run_id(state),
        phase=state.get("app:phase", ""),
        node="outline_build",
        section_count=len(outline.get("sections", [])),
    )
    return {"section_count": len(outline.get("sections", [])), "message": "Outline built"}


async def approve_outline(ctx: Context, node_input: Any) -> dict[str, Any]:
    state = get_state()
    gate = await check_gate("C", state, get_settings())
    state["app:last_gate_C"] = gate.model_dump()
    return await _resolve_approval(ctx, gate, state)


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
        await _publish(
            "section.generated",
            run_id=_run_id(state),
            section=section,
            draft=draft,
            section_title=section.get("title", ""),
            message=f"Drafted section {section.get('title', '')[:80]}",
        )

    state["app:drafts"] = drafts
    state["app:phase"] = "drafting"
    return {"sections_drafted": len(drafts), "message": f"Drafted {len(drafts)} sections"}


async def outline_not_required(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Bridge node for outline gates that are not required."""
    return {"message": "Outline approval not required"}


async def verify_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Real verification: citation entailment + semantic check via Verifier agent."""
    state = get_state()
    drafts = state.get("app:drafts", [])
    claims = state.get("app:claims", [])
    evidence = state.get("app:evidence", [])

    if not drafts:
        result = {"blocking_findings": 1, "passed": False, "message": "No drafts to verify"}
        state["app:verification"] = result
        ctx.route = 0
        return result

    # Heuristic citation entailment check (always runs)
    from deep_research.nodes.verification import verify_draft_citations
    citation_result = verify_draft_citations(drafts, claims, evidence)

    # LLM semantic verification
    from deep_research.agents.verifier import verifier
    semantic_result = await verifier(drafts, claims, evidence)

    # Merge findings
    merged_findings = citation_result.get("findings", []) + semantic_result.get("findings", [])
    blocking = citation_result.get("blocking_findings", 0) + semantic_result.get("blocking_findings", 0)

    result = {
        "findings": merged_findings,
        "blocking_findings": blocking,
        "major_findings": citation_result.get("major_findings", 0) + semantic_result.get("major_findings", 0),
        "passed": blocking == 0,
    }
    state["app:verify_result"] = result
    state["app:verification"] = result
    ctx.route = 1 if result["passed"] else 0
    await _publish(
        "verification.passed" if result["passed"] else "verification.failed",
        run_id=_run_id(state),
        verification=result,
        blocking_findings=blocking,
        passed=result["passed"],
        message="Draft verification completed",
    )
    return result


async def repair_draft(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Repair loop: attempt to fix verification findings (max 2 passes)."""
    state = get_state()
    verification = state.get("app:verification", {})
    repair_count = state.get("app:repair_count", 0)
    max_repair_passes = 2

    if repair_count >= max_repair_passes:
        state["app:phase"] = "failed"
        raise RuntimeError(
            f"Repair loop exceeded max passes ({max_repair_passes}) without reaching a publishable draft"
        )

    from deep_research.nodes.verification import repair_loop

    repair_result = repair_loop(
        findings=verification.get("findings", []),
        drafts=state.get("app:drafts", []),
        max_repairs=max_repair_passes,
    )

    state["app:repair_count"] = repair_count + 1
    state["app:repair_result"] = repair_result
    state["app:phase"] = "repairing"
    _workflow_log(
        logging.INFO,
        "workflow repair attempted",
        run_id=_run_id(state),
        phase=state.get("app:phase", ""),
        node="repair_draft",
        repair_count=state["app:repair_count"],
        result=_result_summary(repair_result),
    )
    return repair_result


async def final_gate_check(ctx: Context, node_input: Any) -> dict[str, Any]:
    state = get_state()
    drafts = state.get("app:drafts", [])
    verification = state.get("app:verification", {})

    # Block publication if verification has blocking findings
    if verification.get("blocking_findings", 0) > 0:
        state["app:final_report_preview"] = ""
        result = {
            "approved": False,
            "message": f"Blocked: {verification['blocking_findings']} blocking findings remain",
        }
        state["app:final_gate_result"] = result
        ctx.route = 0
        return result

    state["app:final_report_preview"] = "\n\n".join(draft.get("content", "") for draft in drafts)[:500]
    gate = await check_gate("D", state, get_settings())
    state["app:last_gate_D"] = gate.model_dump()
    result = await _resolve_approval(ctx, gate, state)
    state["app:final_gate_result"] = result

    if ctx.route == 0:
        state["app:phase"] = "failed"
        raise RuntimeError("Final publication approval was rejected")

    return result


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
    state["app:phase"] = "completed"
    await _publish(
        "report.generated",
        run_id=_run_id(state),
        report_length=len(report),
        section_count=len(drafts),
        claim_count=len(state.get("app:claims", [])),
        message="Final report generated",
    )
    await _publish("run.completed", run_id=_run_id(state), report_length=len(report))
    return {"output_format": "markdown", "report_length": len(report), "message": "Pipeline complete"}


async def publication_not_required(ctx: Context, node_input: Any) -> dict[str, Any]:
    """Bridge node for publication gates that are not required."""
    return {"message": "Publication approval not required"}


_ALL_NODE_FUNCS: list[tuple[str, Any]] = [
    ("scope_classify", scope_classify),
    ("perspective_generate", perspective_generate),
    ("question_graph_build", question_graph_build),
    ("approve_plan", approve_plan),
    ("plan_not_required", plan_not_required),
    ("scheduler_select", scheduler_select),
    ("search_plan_create", search_plan_create),
    ("source_retrieve", source_retrieve),
    ("source_policy_apply", source_policy_apply),
    ("evidence_extract", evidence_extract),
    ("claims_construct", claims_construct),
    ("knowledge_organize", knowledge_organize),
    ("contradictions_search", contradictions_search),
    ("coverage_calculate", coverage_calculate),
    ("moderator", moderator_node),
    ("interventions_apply", interventions_apply),
    ("scope_change_apply", scope_change_apply),
    ("stop_evaluate", stop_evaluate),
    ("outline_build", outline_build),
    ("approve_outline", approve_outline),
    ("outline_not_required", outline_not_required),
    ("draft_generate", draft_generate),
    ("verify_draft", verify_draft),
    ("repair_draft", repair_draft),
    ("final_gate_check", final_gate_check),
    ("publication_not_required", publication_not_required),
    ("render_output", render_output),
]


def _build_edges(nodes: dict[str, FunctionNode]) -> list[Edge]:
    """Build the iterative collaborative workflow edges."""
    n = nodes
    return [
        Edge(from_node=START, to_node=n["scope_classify"]),
        Edge(from_node=n["scope_classify"], to_node=n["perspective_generate"]),
        Edge(from_node=n["perspective_generate"], to_node=n["question_graph_build"]),
        Edge(from_node=n["question_graph_build"], to_node=n["approve_plan"]),
        Edge(from_node=n["approve_plan"], to_node=n["scope_classify"], route=0),
        Edge(from_node=n["approve_plan"], to_node=n["scheduler_select"], route=1),
        Edge(from_node=n["approve_plan"], to_node=n["plan_not_required"], route=2),
        Edge(from_node=n["plan_not_required"], to_node=n["scheduler_select"]),
        Edge(from_node=n["scheduler_select"], to_node=n["search_plan_create"]),
        Edge(from_node=n["search_plan_create"], to_node=n["source_retrieve"]),
        Edge(from_node=n["source_retrieve"], to_node=n["source_policy_apply"]),
        Edge(from_node=n["source_policy_apply"], to_node=n["evidence_extract"]),
        Edge(from_node=n["evidence_extract"], to_node=n["claims_construct"]),
        Edge(from_node=n["claims_construct"], to_node=n["knowledge_organize"]),
        Edge(from_node=n["knowledge_organize"], to_node=n["contradictions_search"]),
        Edge(from_node=n["contradictions_search"], to_node=n["coverage_calculate"]),
        Edge(from_node=n["coverage_calculate"], to_node=n["moderator"]),
        Edge(from_node=n["moderator"], to_node=n["interventions_apply"]),
        Edge(from_node=n["interventions_apply"], to_node=n["scope_change_apply"]),
        Edge(from_node=n["scope_change_apply"], to_node=n["stop_evaluate"], route=0),
        Edge(from_node=n["scope_change_apply"], to_node=n["question_graph_build"], route=1),
        Edge(from_node=n["stop_evaluate"], to_node=n["scheduler_select"], route=0),
        Edge(from_node=n["stop_evaluate"], to_node=n["outline_build"], route=1),
        Edge(from_node=n["outline_build"], to_node=n["approve_outline"]),
        Edge(from_node=n["approve_outline"], to_node=n["outline_build"], route=0),
        Edge(from_node=n["approve_outline"], to_node=n["draft_generate"], route=1),
        Edge(from_node=n["approve_outline"], to_node=n["outline_not_required"], route=2),
        Edge(from_node=n["outline_not_required"], to_node=n["draft_generate"]),
        Edge(from_node=n["draft_generate"], to_node=n["verify_draft"]),
        Edge(from_node=n["verify_draft"], to_node=n["repair_draft"], route=0),
        Edge(from_node=n["verify_draft"], to_node=n["final_gate_check"], route=1),
        Edge(from_node=n["repair_draft"], to_node=n["final_gate_check"]),
        Edge(from_node=n["final_gate_check"], to_node=n["repair_draft"], route=0),
        Edge(from_node=n["final_gate_check"], to_node=n["render_output"], route=1),
        Edge(from_node=n["final_gate_check"], to_node=n["publication_not_required"], route=2),
        Edge(from_node=n["publication_not_required"], to_node=n["render_output"]),
    ]


def build_research_workflow() -> Workflow:
    """Build the complete research workflow."""
    node_list = [FunctionNode(func=_instrument_node(name, func), name=name) for name, func in _ALL_NODE_FUNCS]
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
