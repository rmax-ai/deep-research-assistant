# Deep Research Assistant

**Enterprise-grade governed research runtime built on Google ADK 2.0**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![ADK 2.0](https://img.shields.io/badge/ADK-2.2.0+-green.svg)](https://github.com/google/adk-python)

Converts broad research requests into governed, inspectable, reproducible research workflows. Implements a staged epistemic pipeline: intent → scope → perspectives → questions → search → evidence → claims → contradictions → coverage analysis → outline → drafts → verification → approval → final report.

**The fundamental unit of quality is a supported, qualified, and traceable claim — not a polished paragraph.**

## Quickstart (Coming in Phase 1)

```bash
# Create a research run
curl -X POST http://localhost:8080/v1/research-runs \
  -H "Content-Type: application/json" \
  -d '{
    "objective": {
      "title": "Secure agent runtime analysis",
      "primary_question": "Which architectural controls are required for a secure enterprise agent runtime?"
    },
    "mode": "review_first"
  }'

# Inspect progress
curl http://localhost:8080/v1/research-runs/{run_id}

# Export final report
curl -X POST http://localhost:8080/v1/research-runs/{run_id}/exports \
  -d '{"format": "markdown"}'
```

## Architecture

The system separates concerns across three planes:

| Plane | Responsibility |
|-------|---------------|
| **Governance** | Identity, authorization, policy, approvals, audit |
| **Workflow** | Deterministic orchestration, scheduling, budgeting, persistence |
| **Cognitive** | 14 bounded LLM agents with narrow mandates and structured outputs |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full system architecture, component diagrams, trust boundaries, and data model.

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full system architecture, 14 agents, data model, workflow topology, trust boundaries |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | 12-threat structured analysis with attack paths, controls, and residual risk |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 7-phase implementation plan with deliverables, dependencies, and exit criteria |
| [`AGENTS.md`](AGENTS.md) | Code conventions for all AI coding agents working on this project |

## Agent Roster

| Agent | Role | Model Tier |
|-------|------|-----------|
| Research Director | Scope interpretation, plan proposal | Reasoning |
| Perspective Planner | Discover research lenses | Reasoning |
| Question Architect | Build initial question graph | Reasoning |
| Research Moderator | Detect stagnation, rebalance breadth/depth | Reasoning |
| Query Planner | Convert questions to executable searches | Fast |
| Source Appraiser | Claim-relative authority assessment | Hybrid |
| Evidence Curator | Extract evidence fragments | Reasoning |
| Claim Builder | Convert evidence to atomic claims | Reasoning |
| Counter-Evidence | Search for contradictions | Reasoning |
| Knowledge Organizer | Maintain conceptual hierarchy | Fast |
| Outline Architect | Structure reports from validated claims | Reasoning |
| Section Writer | Generate prose from approved claims | Reasoning |
| Verifier | Independent proposition verification | Verification |
| Executive Synthesizer | Concise executive synthesis | Reasoning |

## Key Principles

- **Research is a workflow** — stateful graph with explicit transitions, not a chatbot
- **Agents are bounded workers** — narrow mandates, constrained tools, structured outputs
- **Questions are first-class objects** — stored, linked, ranked, resolved, reopened
- **Claims are first-class objects** — reports generated from validated claim objects
- **Evidence and inference are distinct** — what a source states ≠ what's extracted ≠ what's inferred
- **Human review at semantic boundaries** — not after every model call

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0: Architecture Spike | 🔴 Backlog | ADK 2.0 workflow skeleton, one end-to-end demo |
| 1: Evidence-First MVP | 🔴 Backlog | Core pipeline: scope → evidence → claims → report |
| 2: STORM-Grade Research | 🔴 Backlog | Evidence-conditioned follow-up questions, semantic stopping |
| 3: Co-STORM Collaboration | 🔴 Backlog | Live research frontier, user interventions, approval center |
| 4: Epistemic Reliability | 🔴 Backlog | Contradiction detection, confidence model, independent verification |
| 5: Enterprise Governance | 🔴 Backlog | Identity, policy, MCP, audit, tenant isolation |
| 6: Continuous Research | 🔴 Backlog | Scheduled watches, reusable skills, knowledge publishing |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for detailed deliverables per phase.

## Tech Stack

- **Runtime:** Google ADK 2.0 (Python)
- **Database:** PostgreSQL (production) / SQLite (development)
- **Models:** Google Gemini (3-flash-preview fast tier, 2.5-pro reasoning/verification)
- **Build:** uv + Hatch + pyproject.toml
- **Testing:** pytest + pytest-asyncio
- **Linting:** ruff (format + check) + mypy strict
- **Observability:** OpenTelemetry + structlog

## License

MIT — see [LICENSE](LICENSE) for details.
