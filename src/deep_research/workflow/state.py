"""Shared pipeline state backed by a context-local dict.

ADK 2.0 Workflow nodes run in isolated contexts where module-level
variables from the defining module may not be accessible. This
dedicated state module provides a clean import path.

Usage:
    from deep_research.workflow.state import get_state, reset_state
    state = get_state()
    state["app:key"] = value
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_pipeline_state: ContextVar[dict[str, Any]] = ContextVar("pipeline_state", default={})


def get_state() -> dict[str, Any]:
    """Return the current pipeline state dict."""
    return _pipeline_state.get()


def set_state(state: dict[str, Any]) -> None:
    """Replace the current pipeline state dict."""
    _pipeline_state.set(state)


def reset_state() -> None:
    """Reset the pipeline state for the current context."""
    _pipeline_state.set({})
