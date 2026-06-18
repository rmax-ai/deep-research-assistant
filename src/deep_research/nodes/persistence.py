"""Persistence node — saves and loads research state.

Handles durable storage of research run state, claims, evidence,
and sources. Uses SQLAlchemy async for production, in-memory dict
for development/testing.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store for development (replaced by SQLAlchemy in Phase 1+)
_memory_store: dict[str, dict[str, Any]] = {}


async def save_run_state(run_id: str, state: dict[str, Any]) -> None:
    """Persist the current research run state.

    Args:
        run_id: The research run ID.
        state: Full state dict to save.
    """
    _memory_store[run_id] = dict(state)
    logger.debug("saved state for run %s (%d keys)", run_id, len(state))


async def load_run_state(run_id: str) -> dict[str, Any] | None:
    """Load a previously saved research run state.

    Args:
        run_id: The research run ID.

    Returns:
        The saved state dict, or None if not found.
    """
    state = _memory_store.get(run_id)
    if state is not None:
        logger.debug("loaded state for run %s (%d keys)", run_id, len(state))
    return state


async def delete_run_state(run_id: str) -> None:
    """Delete a research run's state.

    Args:
        run_id: The research run ID.
    """
    _memory_store.pop(run_id, None)
    logger.debug("deleted state for run %s", run_id)


async def list_runs() -> list[str]:
    """List all saved run IDs.

    Returns:
        List of run IDs.
    """
    return list(_memory_store.keys())
