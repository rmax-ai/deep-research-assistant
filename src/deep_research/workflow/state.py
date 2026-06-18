"""Shared pipeline state — module-level dict for workflow state.

ADK 2.0 Workflow nodes run in isolated contexts where module-level
variables from the defining module may not be accessible. This
dedicated state module provides a clean import path.

Usage:
    from deep_research.workflow.state import get_state, reset_state
    state = get_state()
    state["app:key"] = value
"""

from __future__ import annotations

from typing import Any

_pipeline_state: dict[str, Any] = {}


def get_state() -> dict[str, Any]:
    """Return the shared pipeline state dict."""
    return _pipeline_state


def reset_state() -> None:
    """Reset the pipeline state for a new run."""
    _pipeline_state.clear()
