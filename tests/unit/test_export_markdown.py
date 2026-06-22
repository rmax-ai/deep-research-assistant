"""Tests for markdown export reference rewriting."""

from __future__ import annotations

from deep_research.api.routes import _build_export_markdown


def test_export_only_includes_referenced_sources_and_renumbers_citations() -> None:
    run_data = {
        "objective": {"title": "Reference Test"},
        "report": "# Reference Test\n\nThis finding is supported by prior evidence [3] and [2].",
        "state": {
            "app:sources": [
                {
                    "source_id": "source-1",
                    "title": "Unused Source",
                    "url": "https://example.com/unused",
                    "source_type": "primary",
                },
                {
                    "source_id": "source-2",
                    "title": "Second Source",
                    "url": "https://example.com/second",
                    "source_type": "primary",
                },
                {
                    "source_id": "source-3",
                    "title": "Third Source",
                    "url": "https://example.com/third",
                    "source_type": "primary",
                },
            ],
            "app:evidence": [
                {"evidence_id": "e-1", "source_id": "https://example.com/unused"},
                {"evidence_id": "e-2", "source_id": "https://example.com/second"},
                {"evidence_id": "e-3", "source_id": "https://example.com/third"},
            ],
            "app:claims": [],
        },
    }

    exported = _build_export_markdown(run_data)

    assert "supported by prior evidence [1] and [2]" in exported
    assert "## Referenced Sources" in exported
    assert "https://example.com/third" in exported
    assert "https://example.com/second" in exported
    assert "https://example.com/unused" not in exported
