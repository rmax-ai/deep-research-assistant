"""Verification-specific unit tests."""

from __future__ import annotations

from deep_research.nodes.verification import verify_draft_citations


def test_verify_draft_citations_accepts_stable_claim_references() -> None:
    drafts = [
        {
            "section_title": "Findings",
            "content": "A supported finding. [claim:c-1]",
            "cited_claim_ids": ["c-1"],
        }
    ]
    claims = [
        {
            "claim_id": "c-1",
            "text": "ADK supports workflow governance controls",
            "evidence_ids": ["e-1"],
        }
    ]
    evidence = [
        {
            "evidence_id": "e-1",
            "exact_excerpt": "ADK supports workflow governance controls.",
        }
    ]

    result = verify_draft_citations(drafts, claims, evidence)

    assert result["passed"] is True
    assert result["findings"] == []


def test_verify_draft_citations_blocks_legacy_numeric_citations() -> None:
    drafts = [
        {
            "section_title": "Findings",
            "content": "A supported finding. [1]",
            "cited_claim_ids": [],
        }
    ]

    result = verify_draft_citations(drafts, claims=[], evidence=[])

    assert result["passed"] is False
    assert result["blocking_findings"] == 1
    assert result["findings"][0]["type"] == "legacy_numeric_citation"


def test_verify_draft_citations_blocks_unknown_claim_reference() -> None:
    drafts = [
        {
            "section_title": "Findings",
            "content": "A supported finding. [claim:c-404]",
            "cited_claim_ids": ["c-404"],
        }
    ]

    result = verify_draft_citations(drafts, claims=[], evidence=[])

    assert result["passed"] is False
    assert result["blocking_findings"] == 1
    assert result["findings"][0]["type"] == "missing_claim"
