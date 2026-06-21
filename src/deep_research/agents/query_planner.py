"""Query Planner Agent — converts questions into executable search plans.

Generates multiple query strategies per question targeting
different source types and perspectives.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents import generate_structured, is_llm_available, parse_json_response

logger = logging.getLogger(__name__)

QUERY_PLANNER_INSTRUCTION = """You are a Query Planner for an enterprise research system.
Convert research questions into concrete, executable search queries.

## Your Task
Given a research question, generate 3-5 search query variants using different strategies.

## Query Strategies
- **exact**: The question verbatim or close to it
- **synonyms**: Alternative terminology for the same concept
- **official_docs**: "site:domain.com keyword" or "official documentation keyword"
- **standards**: Search for relevant standards (RFC, ISO, NIST, OWASP, etc.)
- **repository**: GitHub/GitLab search for code, issues, discussions
- **academic**: Scholarly search terms for papers and proceedings
- **failure_incident**: Search for bugs, CVEs, incident reports, postmortems
- **comparative**: "X vs Y" or "X alternative" queries
- **counter_evidence**: Search specifically for evidence that contradicts expected findings
- **date_constrained**: Version with date filters for recent information

## Output Format
Return ONLY a JSON object. No markdown, no explanation.

{
  "queries": [
    {
      "raw_query": "the exact search string",
      "strategy": "exact|synonyms|official_docs|standards|repository|academic|failure_incident|comparative|counter_evidence|date_constrained",
      "rationale": "why this query strategy"
    },
    ...
  ]
}

## Rules
1. Always include at least one exact/close query and one counter_evidence query
2. For technical topics, include official_docs and standards queries
3. For security topics, include failure_incident queries
4. Queries should be specific enough to return relevant results
5. Use technical terminology where appropriate (the system can handle it)"""


async def query_planner(
    question: dict[str, Any],
    model: str = "gemini-2.5-flash",
) -> list[dict[str, Any]]:
    """Generate search queries for a research question.

    Args:
        question: Question dict with text, question_type, perspective.
        model: Gemini model (fast tier OK).

    Returns:
        List of query dicts with raw_query, strategy, rationale.
    """
    if not is_llm_available():
        return _stub_queries(question)

    prompt = f"""Research question: {question.get('text', '')}
Question type: {question.get('question_type', 'unknown')}
Perspective: {question.get('perspective', 'unknown')}

Generate search queries for this question."""

    try:
        response = await generate_structured(
            prompt=prompt,
            model=model,
            system_instruction=QUERY_PLANNER_INSTRUCTION,
            temperature=0.2,
        )
        result = parse_json_response(response, default={"queries": []})
        queries = result.get("queries", []) if isinstance(result, dict) else []
        logger.info("query_planner: generated %d queries for %r", len(queries), question.get("text", "")[:60])
        return queries if isinstance(queries, list) else _stub_queries(question)
    except Exception as exc:
        logger.error("query_planner failed: %s", exc)
        return _stub_queries(question)


def _stub_queries(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stub queries for offline mode."""
    text = question.get("text", "")
    return [
        {"raw_query": text, "strategy": "exact", "rationale": "Direct search"},
        {"raw_query": f"{text} documentation", "strategy": "official_docs", "rationale": "Official docs"},
        {"raw_query": f"{text} issues problems", "strategy": "failure_incident", "rationale": "Known issues"},
    ]
