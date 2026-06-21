"""Continuous watch mode — scheduled re-execution of saved research specs.

Supports delta detection: new sources, changed content, invalidated claims.
"""

from __future__ import annotations

from typing import Any, TypedDict


class WatchSpec(TypedDict, total=False):
    watch_id: str
    run_id: str
    schedule: str  # cron expression
    last_run: str | None
    enabled: bool
    research_spec: dict[str, Any]
    last_source_hashes: dict[str, str]
    last_claims: list[dict[str, Any]]


class WatchResult(TypedDict, total=False):
    watch_id: str
    executed_at: str
    new_sources: list[dict[str, Any]]
    changed_sources: list[str]
    invalidated_claims: list[str]
    confidence_changes: list[dict[str, Any]]
    new_contradictions: list[dict[str, Any]]
    recommendations: list[str]


# In-memory watch store
_watch_store: dict[str, WatchSpec] = {}


def reset_watch_store() -> None:
    _watch_store.clear()


def create_watch(spec: WatchSpec) -> WatchSpec:
    """Register a new research watch."""
    watch_id = spec.get("watch_id", f"watch-{len(_watch_store):03d}")
    spec["watch_id"] = watch_id
    spec["enabled"] = spec.get("enabled", True)
    _watch_store[watch_id] = spec
    return spec


def get_watch(watch_id: str) -> WatchSpec | None:
    return _watch_store.get(watch_id)


def list_watches() -> list[WatchSpec]:
    return list(_watch_store.values())


def detect_deltas(
    previous_hashes: dict[str, str],
    current_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Detect new and changed sources since last watch execution.

    Returns: {new_sources, changed_sources, unchanged_count}
    """
    from deep_research.nodes.deduplication import compute_content_hash

    new_sources = []
    changed_sources = []
    current_ids = set()

    for src in current_sources:
        sid = src.get("source_id", "")
        current_ids.add(sid)
        content = str(src.get("snippet", src.get("content", "")))
        current_hash = compute_content_hash(content)

        if sid not in previous_hashes:
            new_sources.append({**src, "content_hash": current_hash})
        elif previous_hashes[sid] != current_hash:
            changed_sources.append(sid)

    return {
        "new_sources": new_sources,
        "changed_sources": changed_sources,
        "unchanged_count": len(current_ids) - len(new_sources) - len(changed_sources),
    }


def invalidate_claims(
    changed_source_ids: list[str],
    claims: list[dict[str, Any]],
) -> list[str]:
    """Invalidate claims that depend on changed sources.

    Returns list of invalidated claim IDs.
    """
    invalidated = []
    changed_set = set(changed_source_ids)

    for claim in claims:
        evidence_ids = claim.get("evidence_ids", [])
        if any(eid in changed_set for eid in evidence_ids):
            claim["status"] = "stale"
            invalidated.append(claim.get("claim_id", ""))

    # Cascade to derived claims
    for claim in claims:
        if claim.get("claim_id") in invalidated:
            continue
        supporting = claim.get("supporting_claim_ids", [])
        if any(scid in invalidated for scid in supporting):
            claim["status"] = "stale"
            invalidated.append(claim.get("claim_id", ""))

    return invalidated
