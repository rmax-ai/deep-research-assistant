"""Source deduplication and independence clustering.

Deterministic node — groups sources by publisher/author/domain for independence scoring.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse


def _normalize_publisher(publisher: str) -> str:
    """Normalize publisher name for clustering."""
    if not publisher:
        return ""
    p = publisher.lower().strip()
    # Remove common suffixes
    for suffix in (" inc.", " inc", " llc", " ltd.", " ltd", " corp.", " corp", " gmbh", " s.a.", " ag"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
    return re.sub(r"[^a-z0-9]", "", p)


def _extract_domain(url: str) -> str:
    """Extract normalized domain from URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove www prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.lower()
    except Exception:
        return url.lower()


def _extract_publisher_from_url(url: str) -> str:
    """Extract a publisher-like name from a domain."""
    domain = _extract_domain(url)
    if not domain:
        return ""
    # Remove TLD
    parts = domain.split(".")
    if len(parts) >= 2:
        return parts[-2]  # e.g., "github" from "github.com"
    return domain


def cluster_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign independence_cluster_id to each source.

    Groups sources by publisher, domain, and author. Sources from the same
    organization receive the same cluster ID. Multiple derivative articles
    from the same publisher count as one independence cluster.

    Args:
        sources: List of source dicts with {source_id, publisher, url, author}.

    Returns:
        Sources with independence_cluster_id added.
    """
    clusters: dict[str, str] = {}  # normalized key → cluster_id

    for source in sources:
        publisher = str(source.get("publisher", ""))
        url = str(source.get("canonical_uri", source.get("url", "")))
        author = str(source.get("author", ""))

        # Build clustering key: prefer publisher, fall back to domain
        norm_pub = _normalize_publisher(publisher)
        domain = _extract_domain(url)

        if norm_pub:
            key = f"pub:{norm_pub}"
        elif domain:
            key = f"domain:{domain}"
        else:
            # Fall back to URL hash
            key = f"url:{hashlib.md5(url.encode()).hexdigest()[:8]}"

        # Also check author for clustering
        if author and not norm_pub:
            norm_author = author.lower().strip()
            if norm_author:
                author_key = f"author:{norm_author}"
                if author_key not in clusters:
                    clusters[author_key] = f"cluster-{len(clusters):03d}"
                source["independence_cluster_id"] = clusters[author_key]
                continue

        if key not in clusters:
            clusters[key] = f"cluster-{len(clusters):03d}"

        source["independence_cluster_id"] = clusters[key]

    return sources


def deduplicate_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate sources by URL and title similarity.

    Args:
        sources: List of source dicts.

    Returns:
        Deduplicated source list.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []

    for source in sources:
        url = str(source.get("canonical_uri", source.get("url", "")))
        title = str(source.get("title", "")).lower().strip()

        # URL dedup
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Title dedup (normalized)
        norm_title = re.sub(r"\s+", " ", title)
        if norm_title in seen_titles:
            continue
        if norm_title:
            seen_titles.add(norm_title)

        unique.append(source)

    return unique


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode()).hexdigest()


def detect_changed_sources(
    previous_hashes: dict[str, str],
    current_sources: list[dict[str, Any]],
) -> list[str]:
    """Detect sources whose content has changed.

    Args:
        previous_hashes: Dict of source_id → content_hash from previous run.
        current_sources: Current source list with content_hash field.

    Returns:
        List of source_ids with changed content.
    """
    changed = []
    for src in current_sources:
        sid = src.get("source_id", "")
        current_hash = src.get("content_hash", "")
        prev_hash = previous_hashes.get(sid, "")
        if prev_hash and current_hash and prev_hash != current_hash:
            changed.append(sid)
    return changed
