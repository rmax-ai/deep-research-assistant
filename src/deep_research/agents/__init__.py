"""Shared LLM client and utilities for all agents.

Provides a singleton Google GenAI client and helpers for
structured output parsing with fallback patterns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_client: Any = None


def get_client() -> Any:
    """Return a singleton Google GenAI client."""
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client()
    return _client


def is_llm_available() -> bool:
    """Check if Gemini API is configured."""
    return bool(os.environ.get("GOOGLE_API_KEY"))


async def generate_structured(
    prompt: str,
    model: str = "gemini-2.5-pro",
    system_instruction: str | None = None,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
) -> str:
    """Generate text with Gemini and return the raw response.

    Args:
        prompt: The user prompt / content to process.
        model: Gemini model ID.
        system_instruction: Optional system-level instruction.
        temperature: Sampling temperature (0.0-1.0).
        max_output_tokens: Maximum tokens in response.

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If GOOGLE_API_KEY is not set.
    """
    if not is_llm_available():
        raise RuntimeError(
            "GOOGLE_API_KEY not set. Set it to use LLM-backed agents."
        )

    client = get_client()
    config = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_instruction:
        config["system_instruction"] = system_instruction

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return response.text


def parse_json_response(text: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse JSON from model response with robust error recovery.

    Handles:
    - Code-fenced JSON (```json ... ```)
    - Bare JSON objects
    - Trailing commas
    - Leading/trailing whitespace

    Args:
        text: Raw model response text.
        default: Default value if parsing fails completely.

    Returns:
        Parsed dict, or default (empty dict if None).
    """
    if default is None:
        default = {}

    # Try extracting from code fence
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Find the end of the fence
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing fence
        cleaned = "\n".join(lines)

    # Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    try:
        start = cleaned.index("{")
        end = cleaned.rindex("}") + 1
        return json.loads(cleaned[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse JSON from response: %.200s", text)
        return default
