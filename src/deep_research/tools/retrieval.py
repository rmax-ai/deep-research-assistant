"""URL content retrieval tool.

Fetches and extracts text content from web pages.
Used after search to retrieve full source content for evidence extraction.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRIEVAL_TIMEOUT = 20.0
MAX_CONTENT_LENGTH = 50_000

USER_AGENT = (
    "Mozilla/5.0 (compatible; DeepResearchAssistant/0.1; +https://github.com/rmax-ai/deep-research-assistant)"
)


async def url_retrieve(
    url: str,
    max_length: int = MAX_CONTENT_LENGTH,
    tool_context: Any | None = None,
) -> dict[str, Any]:
    """Retrieve and extract text content from a URL.

    Args:
        url: The URL to retrieve.
        max_length: Maximum content length in characters.
        tool_context: ADK tool context for state access.

    Returns:
        Dict with 'url', 'title', 'content', 'content_length', 'status_code'.
    """
    try:
        async with httpx.AsyncClient(timeout=RETRIEVAL_TIMEOUT) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()

        html = response.text

        # Extract title
        title = _extract_title(html)

        # Extract text content (basic: strip tags)
        content = _html_to_text(html)
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated]"

        logger.info("url_retrieve: %s → %d chars", url, len(content))
        return {
            "url": url,
            "title": title,
            "content": content,
            "content_length": len(content),
            "status_code": response.status_code,
        }

    except Exception as exc:
        logger.warning("url_retrieve failed for %s: %s", url, exc)
        return {
            "url": url,
            "title": "",
            "content": "",
            "content_length": 0,
            "status_code": getattr(exc, "status_code", 0),
            "error": str(exc),
        }


def _extract_title(html: str) -> str:
    """Extract the <title> from HTML."""
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return _strip_html(match.group(1))
    return ""


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    import re

    # Remove scripts and styles
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block elements with newlines
    html = re.sub(r"</?(div|p|h[1-6]|li|tr|br|hr)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'")
    # Collapse whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'")
    return text.strip()
