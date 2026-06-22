"""Centralized logging configuration for the Deep Research Assistant."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deep_research.settings import get_settings

_CONFIGURED = False

_RESERVED_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class RunContextFilter(logging.Filter):
    """Attach workflow context fields to log records when available."""

    def filter(self, record: logging.LogRecord) -> bool:
        from deep_research.policies.identity import get_current_principal
        from deep_research.workflow.state import get_state

        state = get_state()
        principal = get_current_principal(state)

        if not getattr(record, "run_id", None):
            run_id = principal.get("run_id") or state.get("app:run_id", "")
            if run_id:
                record.run_id = run_id
        if not getattr(record, "tenant_id", None):
            tenant_id = principal.get("tenant_id")
            if tenant_id:
                record.tenant_id = tenant_id
        if not getattr(record, "user_id", None):
            user_id = principal.get("user_id")
            if user_id:
                record.user_id = user_id
        if not getattr(record, "node_path", None):
            node_path = principal.get("node_path") or state.get("app:current_node")
            if node_path:
                record.node_path = node_path
        if not getattr(record, "phase", None):
            phase = state.get("app:phase")
            if phase:
                record.phase = phase
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utcnow(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


class ConsoleFormatter(logging.Formatter):
    """Format log records for local development."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname} {record.name}: {record.getMessage()}"
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_LOG_RECORD_FIELDS and not key.startswith("_")
        }
        if extras:
            base = f"{base} | {json.dumps(extras, default=str, sort_keys=True)}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(*, force: bool = False) -> None:
    """Configure root logging from application settings."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    settings = get_settings()
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.filters.clear()
    root_logger.setLevel(settings.log_level)
    context_filter = RunContextFilter()
    root_logger.addFilter(context_filter)

    stream_handler = logging.StreamHandler()
    if settings.log_format == "json":
        stream_handler.setFormatter(JsonFormatter())
    else:
        stream_handler.setFormatter(ConsoleFormatter())
    stream_handler.addFilter(context_filter)
    root_logger.addHandler(stream_handler)

    log_file_path = Path(settings.log_file_path)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)

    _CONFIGURED = True


def read_run_logs(run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    """Read JSON log records for one run_id from the configured log file."""
    settings = get_settings()
    log_file_path = Path(settings.log_file_path)
    if not log_file_path.exists():
        return []

    matches: list[dict[str, Any]] = []
    with log_file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("run_id") != run_id:
                continue
            matches.append(payload)

    if limit <= 0:
        return matches
    return matches[-limit:]
