"""Web search tool for the Deep Research Assistant.

Provides search capabilities via Exa using the EXA_API_KEY environment variable.
Returns structured results compatible with the SourceRecord schema.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from deep_research.policies.identity import get_current_principal
from deep_research.settings import get_settings

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 20.0
MAX_RESULTS = 10
EXA_SEARCH_URL = "https://api.exa.ai/search"


async def web_search(
    query: str,
    max_results: int = 5,
    tool_context: Any | None = None,
) -> dict[str, Any]:
    """Search the web for information on a given query using Exa.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1-10).
        tool_context: ADK tool context for state access.

    Returns:
        Dict with 'results' list of normalized source dicts,
        and 'query' and 'total_results' metadata.
    """
    del tool_context

    max_results = min(max(max_results, 1), MAX_RESULTS)
    principal = get_current_principal()
    settings = get_settings()
    api_key = settings.exa_api_key

    if not query.strip():
        return {
            "query": query,
            "total_results": 0,
            "results": [],
            "error": "empty query",
        }

    if not api_key:
        logger.warning("web_search failed for %r: EXA_API_KEY is not configured", query)
        return {
            "query": query,
            "total_results": 0,
            "results": [],
            "error": "EXA_API_KEY is not configured",
        }

    payload = {
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {
            "highlights": True,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            response = await client.post(
                EXA_SEARCH_URL,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        response_payload = response.json()
        raw_results = response_payload.get("results", [])
        results = [_normalize_exa_result(item) for item in raw_results if isinstance(item, dict)]

        logger.info(
            "web_search: query=%r returned %d results",
            query,
            len(results),
            extra={
                "run_id": principal.get("run_id"),
                "user_id": principal.get("user_id"),
                "provider": "exa",
                "request_id": response_payload.get("requestId"),
            },
        )
        return {
            "query": query,
            "total_results": len(results),
            "results": results,
            "request_id": response_payload.get("requestId"),
        }

    except Exception as exc:
        logger.warning("web_search failed for %r: %s", query, exc)
        return {
            "query": query,
            "total_results": 0,
            "results": [],
            "error": str(exc),
        }


def _normalize_exa_result(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Exa result into the workflow's expected source shape."""
    url = str(item.get("url", ""))
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    highlights = item.get("highlights", [])
    snippet = ""
    if isinstance(highlights, list) and highlights:
        snippet = str(highlights[0])
    elif isinstance(item.get("summary"), str):
        snippet = str(item["summary"])
    elif isinstance(item.get("text"), str):
        snippet = str(item["text"])[:500]

    return {
        "title": str(item.get("title", "")),
        "url": url,
        "canonical_uri": url,
        "snippet": snippet,
        "published_date": item.get("publishedDate"),
        "author": item.get("author"),
        "domain": domain,
        "source_type": "web",
        "provider": "exa",
    }


def _extract_between(text: str, start: str, end: str) -> str:
    """Extract text between start and end markers.

    Kept for compatibility with existing unit tests.
    """
    try:
        idx = text.index(start) + len(start)
        end_idx = text.index(end, idx)
        return text[idx:end_idx]
    except ValueError:
        return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags from text.

    Kept for compatibility with existing unit tests.
    """
    import re

    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#x27;", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
