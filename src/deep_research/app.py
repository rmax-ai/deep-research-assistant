"""Deep Research Assistant — Root ADK Application.

Creates the ADK 2.0 Workflow graph that orchestrates the full
14-stage research pipeline.
"""

from __future__ import annotations

from google.adk.workflow import Workflow

from deep_research.telemetry import configure_logging
from deep_research.workflow.graph import build_research_workflow


def create_app() -> Workflow:
    """Create the root ADK application Workflow."""
    configure_logging()
    return build_research_workflow()


# Module-level app instance for ADK runner
app = create_app()
