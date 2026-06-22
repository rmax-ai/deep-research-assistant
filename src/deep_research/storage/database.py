"""Async database bootstrap for durable storage."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from deep_research.settings import get_settings
from deep_research.storage.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_configured_url: str | None = None


async def init_database() -> None:
    """Initialize the async engine and create tables when needed."""
    global _engine, _session_factory, _configured_url

    settings = get_settings()
    database_url = settings.database_url
    if _engine is not None and _session_factory is not None and _configured_url == database_url:
        return

    if _engine is not None:
        await _engine.dispose()

    _engine = create_async_engine(database_url, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _configured_url = database_url

    if settings.environment == "development":
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _ensure_schema(conn)


async def close_database() -> None:
    """Dispose the current engine and clear cached state."""
    global _engine, _session_factory, _configured_url

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _configured_url = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an initialized async session."""
    await init_database()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


async def _ensure_schema(conn: Any) -> None:
    """Apply additive schema updates for local/dev databases."""
    table_info = await conn.execute(text("PRAGMA table_info(research_runs)"))
    columns = {str(row[1]) for row in table_info.fetchall()}
    additions: dict[str, str] = {
        "updated_at": "TEXT",
        "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
        "user_id": "TEXT NOT NULL DEFAULT 'api_user'",
        "workflow_version": "TEXT NOT NULL DEFAULT '1.0.0'",
        "current_node": "TEXT",
        "awaiting_approval_gate": "TEXT",
        "resume_from_checkpoint_id": "TEXT",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "last_policy_decision_id": "TEXT",
    }
    for column, definition in additions.items():
        if column not in columns:
            await conn.execute(text(f"ALTER TABLE research_runs ADD COLUMN {column} {definition}"))
