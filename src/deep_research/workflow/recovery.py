"""Checkpointing and recovery for resumable research runs.

Handles persisting workflow state so that interrupted runs can
be resumed without duplicating completed stages.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def create_checkpoint(
    state: dict[str, Any],
    checkpoint_dir: Path,
    run_id: str,
    node_name: str,
) -> Path:
    """Save a checkpoint of the current workflow state.

    Args:
        state: The full session state dict.
        checkpoint_dir: Directory for checkpoint files.
        run_id: The research run ID.
        node_name: The name of the node that just completed.

    Returns:
        Path to the saved checkpoint file.
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    filename = f"{run_id}_{node_name}_{timestamp}.json"
    path = checkpoint_dir / filename

    checkpoint = {
        "run_id": run_id,
        "node_name": node_name,
        "timestamp": timestamp,
        "state": _serializable_state(state),
    }

    path.write_text(json.dumps(checkpoint, indent=2, default=str))
    logger.info("checkpoint saved: %s", path)
    return path


def _serializable_state(state: dict[str, Any]) -> dict[str, Any]:
    """Convert session state to JSON-serializable form."""
    serializable: dict[str, Any] = {}
    for key, value in state.items():
        if hasattr(value, "dict"):
            serializable[key] = value.dict() if callable(getattr(value, "dict", None)) else str(value)
        elif hasattr(value, "model_dump"):
            serializable[key] = value.model_dump()
        elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
            serializable[key] = value
        else:
            serializable[key] = str(value)
    return serializable


def load_latest_checkpoint(
    checkpoint_dir: Path,
    run_id: str,
) -> dict[str, Any] | None:
    """Load the most recent checkpoint for a run.

    Args:
        checkpoint_dir: Directory containing checkpoint files.
        run_id: The research run ID.

    Returns:
        The checkpoint state dict, or None if no checkpoint found.
    """
    if not checkpoint_dir.exists():
        return None

    # Find most recent checkpoint file for this run
    pattern = f"{run_id}_*.json"
    files = sorted(checkpoint_dir.glob(pattern), reverse=True)
    if not files:
        return None

    latest = files[0]
    logger.info("loading checkpoint: %s", latest)
    checkpoint = json.loads(latest.read_text())
    if not isinstance(checkpoint, dict):
        return None
    state = checkpoint.get("state")
    return state if isinstance(state, dict) else None


def restore_checkpoint(
    state: dict[str, Any],
    resolved_nodes: list[str],
) -> dict[str, Any]:
    """Filter checkpoint state to preserve completed node outputs.

    Args:
        state: The checkpoint state dict.
        resolved_nodes: List of node names whose results have been used.

    Returns:
        State dict with only the results that are safe to restore.
    """
    restored: dict[str, Any] = {}
    for node in resolved_nodes:
        result_key = f"app:{node}_result"
        if result_key in state:
            restored[result_key] = state[result_key]
    return restored
