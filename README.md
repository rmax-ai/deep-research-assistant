# Deep Research Assistant

**Governed multi-agent research runtime built on Google ADK 2.0**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![ADK 2.2.0+](https://img.shields.io/badge/ADK-2.2.0+-green.svg)](https://github.com/google/adk-python)

Deep Research Assistant turns a broad research objective into a bounded, inspectable workflow with explicit scope, question graphs, source retrieval, immutable evidence fragments, claim records, approval gates, verification, and exportable report output.

The core unit of quality is a **supported, qualified, and traceable claim**, not a polished paragraph.

## Current Status

The repository implements the runtime described in the website docs:

- REST API for creating and inspecting research runs
- 27-node ADK workflow with approval branches, repair loops, and resumable execution
- 14 bounded Gemini-backed agents plus deterministic governance and workflow nodes
- Durable run persistence, checkpoints, node execution records, approvals, and audit events
- Streaming events, interventions, concept map projection, logs, and markdown export

Implementation phase status currently matches the website:

| Phase | Status |
|-------|--------|
| 0: Architecture Spike | Complete |
| 1: Evidence-First MVP | Complete |
| 2: STORM-Grade Iterative Research | Complete |
| 3: Co-STORM Collaboration | Complete |
| 4: Epistemic Reliability | Complete |
| 5: Enterprise Governance | Complete |
| 6: Continuous Research | Partial |

## Quickstart

### 1. Install dependencies

```bash
uv sync --extra dev
```

Optional PostgreSQL drivers:

```bash
uv sync --extra dev --extra pg
```

### 2. Configure environment

Start from the checked-in example file:

```bash
cp .env.example .env
```

Full runtime execution needs:

- `DEEP_RESEARCH_GOOGLE_API_KEY` for Gemini-backed agents
- `DEEP_RESEARCH_EXA_API_KEY` for web search

Useful local defaults:

```bash
export DEEP_RESEARCH_GOOGLE_API_KEY="your-google-api-key"
export DEEP_RESEARCH_EXA_API_KEY="your-exa-api-key"
export DEEP_RESEARCH_APPROVALS__MODE="strict"
```

Optional overrides:

```bash
export DEEP_RESEARCH_DATABASE_URL="sqlite+aiosqlite:///deep_research.db"
export DEEP_RESEARCH_LOG_FORMAT="console"
```

### 3. Start the API

```bash
uv run uvicorn deep_research.api.routes:app --host 0.0.0.0 --port 8080
```

### 4. Create a research run

```bash
curl -X POST "http://localhost:8080/v1/research-runs" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": {
      "title": "ADK tool governance deep research demo",
      "primary_question": "How should a Google ADK-based research assistant govern tool usage safely in an enterprise environment?",
      "decision_to_support": "Choose runtime guardrails for production rollout",
      "intended_audience": ["platform engineering", "security architecture"],
      "output_type": "technical_report",
      "desired_depth": "deep"
    },
    "tenant_id": "demo",
    "user_id": "architect-01",
    "mode": "review_first"
  }'
```

### 5. Inspect, approve, and export

```bash
curl "http://localhost:8080/v1/research-runs/$RUN_ID"
curl "http://localhost:8080/v1/research-runs/$RUN_ID/approvals"
curl -X POST "http://localhost:8080/v1/research-runs/$RUN_ID/approvals/A" \
  -H "Content-Type: application/json" \
  -d '{"decision":"approved","rationale":"Scope is acceptable","approver_id":"architect-01"}'
curl "http://localhost:8080/v1/research-runs/$RUN_ID/progress"
curl -N "http://localhost:8080/v1/research-runs/$RUN_ID/events"
curl -X POST "http://localhost:8080/v1/research-runs/$RUN_ID/exports?format=markdown"
```

## API Surface

Base URL:

```text
http://localhost:8080/v1
```

Implemented endpoints:

- `POST /v1/research-runs`
- `GET /v1/research-runs/{run_id}`
- `GET /v1/research-runs/{run_id}/graph`
- `GET /v1/research-runs/{run_id}/frontier`
- `GET /v1/research-runs/{run_id}/progress`
- `GET /v1/research-runs/{run_id}/events`
- `GET /v1/research-runs/{run_id}/logs`
- `GET /v1/research-runs/{run_id}/concept-map`
- `POST /v1/research-runs/{run_id}/interventions`
- `GET /v1/research-runs/{run_id}/approvals`
- `POST /v1/research-runs/{run_id}/approvals/{approval_id}`
- `POST /v1/research-runs/{run_id}/exports`

API-created runs persist governance state and enforce approval pauses. In strict mode, required gates move the run into `awaiting_approval` until a decision is submitted and the workflow resumes from the latest checkpoint.

## Architecture

The runtime separates concerns across three planes:

| Plane | Responsibility |
|-------|---------------|
| Governance | Identity propagation, policy evaluation, approvals, audit |
| Workflow | Deterministic orchestration, scheduling, budgets, checkpoints, recovery |
| Cognitive | 14 bounded LLM agents with narrow roles and structured/text-fallback outputs |

The shipped workflow is a 27-node ADK graph covering:

`scope_classify -> perspective_generate -> question_graph_build -> approve_plan -> scheduler_select -> search_plan_create -> source_retrieve -> source_policy_apply -> evidence_extract -> claims_construct -> knowledge_organize -> contradictions_search -> coverage_calculate -> moderator -> interventions_apply -> scope_change_apply -> stop_evaluate -> outline_build -> approve_outline -> draft_generate -> verify_draft -> repair_draft -> final_gate_check -> render_output`

Key implementation properties:

- Evidence fragments preserve exact excerpts
- Claims are atomic records linked to evidence and sources
- Approval gates A/B/C/D are first-class runtime state
- Audit events are append-only and chain-verified
- Resume behavior restores from persisted checkpoints instead of replaying blindly

## Models and Runtime

Default model routing in the current implementation:

- Fast: `gemini-3-flash-preview`
- Reasoning: `gemini-3.1-pro-preview`
- Verification: `gemini-3.1-pro-preview`

Core stack:

- Google ADK 2.2.0+
- FastAPI
- Pydantic v2
- SQLAlchemy asyncio
- SQLite for local/dev, PostgreSQL in production
- `uv` + Hatch

## Validation

Deterministic validation:

```bash
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src/deep_research
uv run pytest
```

Live Gemini validation remains opt-in:

```bash
uv run pytest -m live_llm
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system architecture and workflow topology
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md): security threat analysis
- [docs/ROADMAP.md](docs/ROADMAP.md): implementation planning background
- [docs/site/src/routes/+page.svx](docs/site/src/routes/+page.svx): website landing-page source
- [docs/site/src/routes/api/+page.svx](docs/site/src/routes/api/+page.svx): website API docs source
- [docs/site/src/routes/architecture/+page.svx](docs/site/src/routes/architecture/+page.svx): website architecture docs source
- [AGENTS.md](AGENTS.md): contributor and coding-agent conventions

## License

MIT. See [LICENSE](LICENSE).
