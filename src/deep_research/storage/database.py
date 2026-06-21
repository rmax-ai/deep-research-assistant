"""Async database bootstrap for durable storage."""

from __future__ import annotations

from collections.abc import AsyncIterator

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
