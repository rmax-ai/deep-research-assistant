"""Checkpointing and recovery for resumable research runs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from deep_research.storage.repositories import (
    create_workflow_checkpoint,
    get_checkpoint,
    get_latest_checkpoint,
)


async def create_checkpoint(
    state: dict[str, Any],
    run_id: str,
    node_name: str,
    node_path: str,
    workflow_version: str,
    logical_input_hash: str,
) -> dict[str, Any]:
    """Persist a checkpoint for the current workflow state."""
    return await create_workflow_checkpoint(
        run_id=run_id,
        node_name=node_name,
        node_path=node_path,
        workflow_version=workflow_version,
        logical_input_hash=logical_input_hash,
        state=deepcopy(state),
    )


async def load_latest_checkpoint_for_run(run_id: str) -> dict[str, Any] | None:
    """Load the most recent checkpoint for a run."""
    return await get_latest_checkpoint(run_id)


async def load_checkpoint(checkpoint_id: str) -> dict[str, Any] | None:
    """Load one checkpoint by id."""
    return await get_checkpoint(checkpoint_id)


def restore_checkpoint(
    checkpoint_state: dict[str, Any],
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore full checkpoint state while preserving current control inputs."""
    restored = deepcopy(checkpoint_state)
    current = current_state or {}
    for key in (
        "app:approval_inputs",
        "app:pending_interventions",
        "app:principal",
        "app:run_mode",
        "app:resumed_after_restart",
        "app:resume_enabled",
        "app:resume_from_node",
    ):
        if key in current:
            restored[key] = deepcopy(current[key])
    return restored
