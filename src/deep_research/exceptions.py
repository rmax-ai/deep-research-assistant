"""Domain exceptions for workflow governance and recovery."""

from __future__ import annotations


class DeepResearchError(Exception):
    """Base class for domain-specific runtime errors."""


class ApprovalRequiredError(DeepResearchError):
    """Raised when workflow execution must pause for human approval."""

    def __init__(self, gate: str):
        super().__init__(f"Approval required for gate {gate}")
        self.gate = gate


class PolicyDeniedError(DeepResearchError):
    """Raised when a policy decision blocks workflow progress."""


class TransientWorkflowError(DeepResearchError):
    """Raised for errors that may succeed when resumed later."""
