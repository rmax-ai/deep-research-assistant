"""In-memory streaming event infrastructure for research runs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

EVENT_TYPES = {
    "run.started",
    "run.resumed",
    "run.failed",
    "scope.proposed",
    "approval.requested",
    "approval.decided",
    "perspective.created",
    "question.created",
    "query.executed",
    "source.accepted",
    "evidence.extracted",
    "claim.created",
    "contradiction.detected",
    "coverage.updated",
    "outline.proposed",
    "section.generated",
    "verification.failed",
    "verification.passed",
    "node.started",
    "node.completed",
    "node.failed",
    "route.selected",
    "budget.checked",
    "policy.applied",
    "policy.denied",
    "stop.evaluated",
    "intervention.submitted",
    "checkpoint.created",
    "checkpoint.restored",
    "report.generated",
    "run.completed",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EventBus:
    """Simple in-memory event bus for dev and tests."""

    def __init__(self) -> None:
        self._events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Publish an event and notify subscribers."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        run_id = str(payload.get("run_id", ""))
        event = {
            "event_type": event_type,
            "payload": payload,
            "run_id": run_id,
            "timestamp": _utcnow().isoformat(),
        }

        async with self._lock:
            self._events_by_run[run_id].append(event)
            subscribers = list(self._subscribers.get(event_type, []))
            subscribers.extend(self._subscribers.get("*", []))

        for callback in subscribers:
            maybe_awaitable = callback(event)
            if maybe_awaitable is not None:
                await maybe_awaitable
        return event

    def subscribe(self, event_type: str, callback: EventCallback) -> Callable[[], None]:
        """Subscribe to one event type or `*` for all events."""
        if event_type != "*" and event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")
        self._subscribers[event_type].append(callback)

        def unsubscribe() -> None:
            subscribers = self._subscribers.get(event_type, [])
            if callback in subscribers:
                subscribers.remove(callback)

        return unsubscribe

    def get_events_since(self, run_id: str, timestamp: str | datetime | None) -> list[dict[str, Any]]:
        """Return all events after the provided timestamp."""
        events = self._events_by_run.get(run_id, [])
        if timestamp is None:
            return list(events)
        since = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)
        return [
            event
            for event in events
            if datetime.fromisoformat(str(event["timestamp"])) > since
        ]

    def reset(self) -> None:
        """Clear all stored events and subscribers."""
        self._events_by_run.clear()
        self._subscribers.clear()


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the process-global event bus."""
    return _event_bus
