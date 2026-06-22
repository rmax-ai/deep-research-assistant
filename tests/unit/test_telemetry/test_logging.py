"""Tests for telemetry logging and event helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from deep_research.telemetry.events import EventBus
from deep_research.telemetry.logging import ConsoleFormatter, JsonFormatter, read_run_logs


class TestLoggingFormatters:
    def test_json_formatter_includes_structured_fields(self):
        formatter = JsonFormatter()
        record = logging.makeLogRecord(
            {
                "name": "deep_research.workflow.graph",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "workflow node completed",
                "run_id": "run-123",
                "node": "scope_classify",
                "status": "ok",
                "duration_ms": 12.5,
            }
        )

        payload = json.loads(formatter.format(record))
        assert payload["message"] == "workflow node completed"
        assert payload["run_id"] == "run-123"
        assert payload["node"] == "scope_classify"
        assert payload["status"] == "ok"
        assert payload["duration_ms"] == 12.5

    def test_console_formatter_renders_structured_fields(self):
        formatter = ConsoleFormatter()
        record = logging.makeLogRecord(
            {
                "name": "deep_research.api.routes",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "research run started",
                "run_id": "run-456",
                "status": "running",
            }
        )

        rendered = formatter.format(record)
        assert "research run started" in rendered
        assert '"run_id": "run-456"' in rendered
        assert '"status": "running"' in rendered

    def test_read_run_logs_filters_by_run_id(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        import deep_research.settings as settings_module

        log_path = tmp_path / "deep_research.log"
        log_path.write_text(
            "\n".join(
                [
                    json.dumps({"run_id": "run-1", "message": "start"}),
                    json.dumps({"run_id": "run-2", "message": "other"}),
                    json.dumps({"run_id": "run-1", "message": "done"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("DEEP_RESEARCH_LOG_FILE_PATH", str(log_path))
        monkeypatch.setattr(settings_module, "_settings", None)

        records = read_run_logs("run-1")
        assert [record["message"] for record in records] == ["start", "done"]


@pytest.mark.asyncio
class TestEventBus:
    async def test_event_bus_accepts_workflow_observability_events(self):
        bus = EventBus()
        events = [
            await bus.publish("node.started", {"run_id": "run-1", "node": "scope_classify"}),
            await bus.publish("route.selected", {"run_id": "run-1", "node": "approve_plan", "route": 1}),
            await bus.publish("stop.evaluated", {"run_id": "run-1", "should_stop": False}),
            await bus.publish("report.generated", {"run_id": "run-1", "report_length": 42}),
        ]

        stored = bus.get_events_since("run-1", None)
        assert [event["event_type"] for event in stored] == [event["event_type"] for event in events]

    async def test_event_bus_notifies_subscribers_for_new_event_types(self):
        bus = EventBus()
        seen: list[str] = []
        done = asyncio.Event()

        async def callback(event: dict[str, object]) -> None:
            seen.append(str(event["event_type"]))
            done.set()

        unsubscribe = bus.subscribe("node.completed", callback)
        try:
            await bus.publish("node.completed", {"run_id": "run-2", "node": "render_output"})
            await asyncio.wait_for(done.wait(), timeout=1.0)
        finally:
            unsubscribe()

        assert seen == ["node.completed"]
