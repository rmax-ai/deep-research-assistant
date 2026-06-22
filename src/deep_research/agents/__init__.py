"""Shared LLM client and utilities for all agents.

Provides a singleton Google GenAI client and helpers for
structured output parsing with fallback patterns.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from deep_research.settings import get_settings

logger = logging.getLogger(__name__)

_client: Any = None

ModelTier = Literal["fast", "reasoning", "verification"]
ModelStage = Literal[
    "perspective_generate",
    "perspective_planner",
    "question_graph_build",
    "question_architect",
    "search_plan_create",
    "query_planner",
    "moderator",
    "follow_up_question_generate",
    "scope_classify",
    "research_director",
    "evidence_extract",
    "evidence_curator",
    "claims_construct",
    "claim_builder",
    "contradictions_search",
    "counter_evidence",
    "outline_build",
    "outline_architect",
    "draft_generate",
    "section_writer",
    "verify_draft",
    "verifier",
    "final_gate_check",
]

_STAGE_TO_TIER: dict[str, ModelTier] = {
    "perspective_generate": "fast",
    "perspective_planner": "fast",
    "question_graph_build": "fast",
    "question_architect": "fast",
    "search_plan_create": "fast",
    "query_planner": "fast",
    "moderator": "fast",
    "follow_up_question_generate": "fast",
    "scope_classify": "reasoning",
    "research_director": "reasoning",
    "evidence_extract": "reasoning",
    "evidence_curator": "reasoning",
    "claims_construct": "reasoning",
    "claim_builder": "reasoning",
    "contradictions_search": "reasoning",
    "counter_evidence": "reasoning",
    "outline_build": "reasoning",
    "outline_architect": "reasoning",
    "draft_generate": "reasoning",
    "section_writer": "reasoning",
    "verify_draft": "verification",
    "verifier": "verification",
    "final_gate_check": "verification",
}


def get_client() -> Any:
    """Return a singleton Google GenAI client."""
    global _client
    if _client is None:
        from google import genai

        settings = get_settings()
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


def is_llm_available() -> bool:
    """Check if Gemini API is configured."""
    return bool(get_settings().google_api_key)


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
        RuntimeError: If DEEP_RESEARCH_GOOGLE_API_KEY is not set.
    """
    if not is_llm_available():
        raise RuntimeError(
            "DEEP_RESEARCH_GOOGLE_API_KEY not set. Set it to use LLM-backed agents."
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


def get_model_for_tier(tier: ModelTier) -> str:
    """Return the configured model identifier for a routing tier."""
    settings = get_settings()
    config = getattr(settings.models, tier)
    return str(config.model_id)


def get_model_for_stage(stage: ModelStage | str) -> str:
    """Return the configured model identifier for a workflow stage."""
    tier = _STAGE_TO_TIER.get(stage)
    if tier is None:
        raise ValueError(f"Unknown model-routed stage: {stage}")
    return get_model_for_tier(tier)


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
