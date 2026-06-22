"""Web search tool for the Deep Research Assistant.

Provides search capabilities via DuckDuckGo (no API key required).
Returns structured results compatible with the SourceRecord schema.

Usage as ADK FunctionTool:
    agent = LlmAgent(tools=[web_search], ...)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from deep_research.policies.identity import get_current_principal

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 15.0
MAX_RESULTS = 10

USER_AGENT = (
    "Mozilla/5.0 (compatible; DeepResearchAssistant/0.1; +https://github.com/rmax-ai/deep-research-assistant)"
)


async def web_search(
    query: str,
    max_results: int = 5,
    tool_context: Any | None = None,
) -> dict[str, Any]:
    """Search the web for information on a given query.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1-10).
        tool_context: ADK tool context for state access.

    Returns:
        Dict with 'results' list of {title, url, snippet} dicts,
        and 'query' and 'total_results' metadata.
    """
    max_results = min(max(max_results, 1), MAX_RESULTS)
    principal = get_current_principal()

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()

        results = _parse_duckduckgo_html(response.text, max_results)

        logger.info(
            "web_search: query=%r returned %d results",
            query,
            len(results),
            extra={"run_id": principal.get("run_id"), "user_id": principal.get("user_id")},
        )
        return {
            "query": query,
            "total_results": len(results),
            "results": results,
        }

    except Exception as exc:
        logger.warning("web_search failed for %r: %s", query, exc)
        return {
            "query": query,
            "total_results": 0,
            "results": [],
            "error": str(exc),
        }


def _parse_duckduckgo_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML results page.

    Extracts title, URL, and snippet from result blocks.
    Uses simple string parsing to avoid external dependencies.
    """
    results: list[dict[str, str]] = []

    # Split on result blocks — DuckDuckGo uses specific class patterns
    blocks = html.split('class="result__body')

    for block in blocks[1:]:  # Skip content before first result
        if len(results) >= max_results:
            break

        title = _extract_between(block, 'class="result__a"', "</a>")
        title = _strip_html(title)

        url = _extract_between(block, 'class="result__url"', "</a>")
        url = _strip_html(url).strip()

        snippet = _extract_between(block, 'class="result__snippet"', "</a>")
        snippet = _strip_html(snippet)

        if title and url:
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet or "",
            })

    return results


def _extract_between(text: str, start: str, end: str) -> str:
    """Extract text between start and end markers."""
    try:
        idx = text.index(start)
        idx += len(start)
        end_idx = text.index(end, idx)
        return text[idx:end_idx]
    except ValueError:
        return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#x27;", "'")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
