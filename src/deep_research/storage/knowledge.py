"""Knowledge-layer publishing — validated claims to long-term memory.

Claims enter new runs as hypotheses requiring freshness checks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class KnowledgeRecord(dict):
    """A published claim in the knowledge layer."""
    pass


# In-memory knowledge store
_knowledge_store: dict[str, KnowledgeRecord] = {}  # claim_id → record


def reset_knowledge_store() -> None:
    _knowledge_store.clear()


def publish_claim(
    claim: dict[str, Any],
    evidence_ids: list[str],
    confidence: float,
    run_id: str,
) -> KnowledgeRecord:
    """Publish a validated claim to the knowledge layer.

    Only call after verification passes.
    """
    record: KnowledgeRecord = {
        "claim_id": claim.get("claim_id", ""),
        "claim_text": claim.get("text", ""),
        "atomic_form": claim.get("atomic_form", ""),
        "evidence_ids": evidence_ids,
        "confidence": confidence,
        "published_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "revalidated_at": None,
        "still_valid": None,
    }
    _knowledge_store[record["claim_id"]] = record
    return record


def retrieve_claims(
    topic: str = "",
    min_confidence: float = 0.5,
) -> list[KnowledgeRecord]:
    """Retrieve published claims, optionally filtered by topic and confidence.

    Claims enter new runs as hypotheses — they must be freshness-checked.
    """
    results = []
    for record in _knowledge_store.values():
        if record.get("confidence", 0) < min_confidence:
            continue
        if topic and topic.lower() not in record.get("claim_text", "").lower():
            continue
        results.append(record)
    return sorted(results, key=lambda r: r.get("confidence", 0), reverse=True)


def revalidate_claim(
    claim_id: str,
    current_evidence_hashes: list[str],
) -> dict[str, Any]:
    """Freshness check: compare current evidence hashes against published record.

    Returns: {still_valid, evidence_changed, needs_reinvestigation}
    """
    record = _knowledge_store.get(claim_id)
    if not record:
        return {"still_valid": False, "error": "claim not found"}

    # Check if any evidence hashes changed
    original_hashes = set(record.get("evidence_ids", []))
    current_hashes = set(current_evidence_hashes)

    changed = original_hashes != current_hashes
    record["revalidated_at"] = datetime.now(UTC).isoformat()

    if changed:
        record["still_valid"] = False
        return {
            "still_valid": False,
            "evidence_changed": True,
            "needs_reinvestigation": True,
            "message": "Supporting evidence has changed — claim requires re-investigation",
        }

    record["still_valid"] = True
    return {
        "still_valid": True,
        "evidence_changed": False,
        "needs_reinvestigation": False,
    }


def get_all_knowledge() -> list[KnowledgeRecord]:
    return list(_knowledge_store.values())
