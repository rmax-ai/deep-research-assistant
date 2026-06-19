"""Scope change handling for collaborative interventions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _unique_extend(items: list[str], values: list[str]) -> list[str]:
    seen = {item.lower() for item in items}
    for value in values:
        if value.lower() not in seen:
            items.append(value)
            seen.add(value.lower())
    return items


def _extract_topics(change: dict[str, Any]) -> list[str]:
    topics = change.get("topics")
    if isinstance(topics, list):
        return [str(topic) for topic in topics if topic]
    topic = change.get("topic")
    return [str(topic)] if topic else []


async def apply_scope_change(run_state: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    """Apply a mid-run scope change and mark question graph for refresh."""
    state = deepcopy(run_state)
    scope = state.setdefault("app:scope", {})
    pending_changes = state.setdefault("app:applied_scope_changes", [])
    change_type = str(change.get("type", ""))

    if change_type == "add_topic":
        scope["included_topics"] = _unique_extend(list(scope.get("included_topics", [])), _extract_topics(change))
    elif change_type == "remove_topic":
        topics = {topic.lower() for topic in _extract_topics(change)}
        scope["included_topics"] = [
            topic for topic in scope.get("included_topics", []) if topic.lower() not in topics
        ]
        scope["excluded_topics"] = _unique_extend(list(scope.get("excluded_topics", [])), list(topics))
    elif change_type == "add_perspective":
        perspective = change.get("perspective")
        if perspective:
            state.setdefault("app:proposed_perspectives", []).append(perspective)
            state.setdefault("app:perspectives", []).append(perspective)
    elif change_type == "change_budget":
        proposed_budget = state.setdefault("app:research_plan", {}).setdefault("proposed_budget", {})
        for key in ("searches", "opened_sources", "max_cost", "max_wall_time_seconds"):
            if key in change:
                proposed_budget[key] = change[key]
    else:
        raise ValueError(f"Unsupported scope change type: {change_type}")

    state["app:scope_replan_required"] = True
    state["app:questions_version"] = int(state.get("app:questions_version", 0)) + 1
    pending_changes.append(change)
    return state
