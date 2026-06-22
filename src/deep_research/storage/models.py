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
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, default="api_user")
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
    workflow_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    current_node: Mapped[str | None] = mapped_column(String(128), nullable=True)
    awaiting_approval_gate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resume_from_checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_policy_decision_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WorkflowCheckpointRecord(Base):
    """Persisted workflow checkpoint."""

    __tablename__ = "workflow_checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False)
    node_path: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(32), nullable=False)
    logical_input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class WorkflowNodeExecutionRecord(Base):
    """Persisted node execution metadata for idempotent replay."""

    __tablename__ = "workflow_node_executions"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False)
    node_path: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(32), nullable=False)
    logical_input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEventRecord(Base):
    """Append-only audit record."""

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    principal_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chain_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class ApprovalDecisionRecord(Base):
    """First-class persisted approval decision state."""

    __tablename__ = "approval_decisions"

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(32), nullable=False)
    gate: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approver_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    display_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    decided_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
