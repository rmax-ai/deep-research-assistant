"""SQLAlchemy models for durable run storage."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative model."""


class ResearchRunRecord(Base):
    """Persisted research run state."""

    __tablename__ = "research_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="planning")
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    objective_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    report: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approvals_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    interventions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    questions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
