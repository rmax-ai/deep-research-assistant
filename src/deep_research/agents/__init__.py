"""Shared LLM client and utilities for all agents.

Provides a singleton Google GenAI client and helpers for
structured output parsing with fallback patterns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Literal

from deep_research.settings import get_settings

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
    model: str | None = None,
    system_instruction: str | None = None,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
    timeout_seconds: int | None = None,
) -> str:
    """Generate text with Gemini and return the raw response.

    Args:
        prompt: The user prompt / content to process.
        model: Gemini model ID. Defaults to the configured reasoning tier.
        system_instruction: Optional system-level instruction.
        temperature: Sampling temperature (0.0-1.0).
        max_output_tokens: Maximum tokens in response.
        timeout_seconds: Optional timeout for the model call.

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If GOOGLE_API_KEY is not set.
    """
    if not is_llm_available():
        raise RuntimeError(
            "GOOGLE_API_KEY not set. Set it to use LLM-backed agents."
        )

    resolved_model = model or get_model_for_tier("reasoning")
    client = get_client()
    config: dict[str, object] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_instruction:
        config["system_instruction"] = system_instruction

    timeout = timeout_seconds or get_settings().workflow.llm_timeout_seconds

    response = await _invoke_model(
        client=client,
        model=resolved_model,
        prompt=prompt,
        config=config,
        timeout=timeout,
    )
    text = _extract_response_text(response)
    if _should_retry_structured_response(text, response):
        retry_config = dict(config)
        retry_config["max_output_tokens"] = max(int(max_output_tokens) * 2, 32)
        response = await _invoke_model(
            client=client,
            model=resolved_model,
            prompt=prompt,
            config=retry_config,
            timeout=timeout,
        )
        text = _extract_response_text(response)

    if not text:
        raise RuntimeError("Model returned no text content")
    return text


def get_model_for_tier(tier: Literal["fast", "reasoning", "verification"]) -> str:
    """Return the configured model identifier for a routing tier."""
    settings = get_settings()
    config = getattr(settings.models, tier)
    return str(config.model_id)


async def _invoke_model(
    client: Any,
    model: str,
    prompt: str,
    config: dict[str, object],
    timeout: int,
) -> Any:
    """Run a blocking Gemini call in a thread with an async timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=prompt,
                config=config,
            ),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise RuntimeError(f"LLM call timed out after {timeout}s") from exc


def _extract_response_text(response: Any) -> str:
    """Extract text from Gemini responses, falling back to candidate parts."""
    direct_text = getattr(response, "text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        texts = [
            part_text.strip()
            for part in parts
            for part_text in [getattr(part, "text", None)]
            if isinstance(part_text, str) and part_text.strip()
        ]
        if texts:
            return "\n".join(texts)

    return ""


def _response_hit_max_tokens(response: Any) -> bool:
    """Return whether the first candidate stopped because it hit the token cap."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return False
    finish_reason = getattr(candidates[0], "finish_reason", None)
    return str(finish_reason).endswith("MAX_TOKENS")


def _should_retry_structured_response(text: str, response: Any) -> bool:
    """Return whether a structured-output response warrants one retry."""
    if not text:
        return _response_hit_max_tokens(response)
    return _looks_like_truncated_structured_output(text)


def _looks_like_truncated_structured_output(text: str) -> bool:
    """Heuristically detect truncated JSON or fenced JSON output."""
    cleaned = text.strip()
    if not cleaned:
        return False

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        else:
            return True
        cleaned = "\n".join(lines).strip()

    if not cleaned.startswith(("{", "[")):
        return False

    stack: list[str] = []
    in_string = False
    escape = False
    for char in cleaned:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char == "}":
            if not stack or stack.pop() != "{":
                return False
        elif char == "]" and (not stack or stack.pop() != "["):
            return False

    return in_string or bool(stack)


def parse_json_response(text: str, default: Any = None) -> Any:
    """Parse JSON from model response with robust error recovery.

    Handles:
    - Code-fenced JSON (```json ... ```)
    - Bare JSON objects or arrays
    - Trailing commas
    - Leading/trailing whitespace

    Args:
        text: Raw model response text.
        default: Default value if parsing fails completely (None → {}).

    Returns:
        Parsed dict/list, or default.
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
