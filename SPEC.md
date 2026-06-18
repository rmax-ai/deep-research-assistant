# Deep Research Assistant — Specification

**Derived from:** Mega Specification v1.0
**Implementation target:** Google ADK 2.0, Python 3.12+
**Repo:** https://github.com/rmax-ai/deep-research-assistant

---

## Scope

Build an enterprise-grade research assistant that converts a broad research request into a governed, inspectable and reproducible research workflow. The assistant implements a staged epistemic pipeline: intent → scope → research perspectives → question graph → search plans → retrieved sources → evidence extraction → claim construction → contradiction analysis → coverage analysis → outline → section drafts → independent verification → human approval → final report.

The fundamental unit of quality is a supported, qualified and traceable claim — not a polished paragraph.

## Features

### Core Research Pipeline (Phases 0-2)
- ADK 2.0 workflow graph with deterministic and LLM-backed nodes
- 14 bounded agents with narrow mandates and structured outputs
- Typed research-state model (ResearchRun, ResearchObjective, Perspective, QuestionGraph, SourceRecord, EvidenceFragment, Claim, Contradiction)
- Evidence-conditioned follow-up questions (STORM-inspired)
- Multi-perspective topic decomposition (Co-STORM-inspired)
- Semantic research frontier scheduling with information-gain metrics

### Epistemic Reliability (Phase 4)
- Claim–evidence graph with explicit inference tracking
- Source authority and independence scoring (claim-relative)
- Contradiction search and resolution tracking
- Causal-claim verification
- Independent verification with model-family separation

### Collaboration (Phase 3)
- Live research frontier with streaming events
- User interventions (pin questions, challenge claims, adjust scope mid-run)
- Approval gates at semantic boundaries (scope, plan, evidence/outline, publication)

### Enterprise Governance (Phase 5)
- Identity-bound tool execution
- Policy engine with role-to-tool allowlists
- MCP gateway with tool ingestion, normalization, and risk classification
- Immutable audit log
- Tenant isolation
- Prompt-injection defenses

### Continuous Research (Phase 6)
- Scheduled research watches with source-delta detection
- Reusable research skills with progressive disclosure
- Knowledge-layer publishing (validated claims → long-term memory)

## Acceptance Criteria

### Phase 0 — Architecture Spike
- [ ] ADK 2.0 Workflow graph executes end-to-end (scope → render)
- [ ] Session state persists across restarts
- [ ] Event streaming infrastructure functional
- [ ] Research run can be interrupted and resumed without duplicating completed stages

### Phase 1 — Evidence-First MVP
- [ ] All substantive report claims map to claim records
- [ ] All source-derived claims map to evidence fragments
- [ ] Reports survive automated citation-entailment tests
- [ ] REST API supports create, inspect, export operations
- [ ] All 14 agent stubs exist with correct tool allowlists

### Phase 2 — STORM-Grade Iterative Research
- [ ] Evidence-conditioned follow-up questions generated per cycle
- [ ] Research frontier scheduler operates with priority function
- [ ] Compute-matched evaluation demonstrates better coverage than one-shot RAG
- [ ] Stopping conditions include information gain, diversity, and contradiction resolution rate

### Phase 3 — Co-STORM Collaboration
- [ ] Users can steer a running investigation without corrupting workflow state
- [ ] All user interventions become auditable events
- [ ] Approval Center supports Gate A (scope), B (plan), C (evidence/outline), D (recommendation)
- [ ] Streaming events reach UI within 2 seconds

### Phase 4 — Epistemic Reliability
- [ ] Material unsupported-inference rate < 5%
- [ ] Citation entailment > 90%
- [ ] Every high-materiality inferred claim has explicit inference record
- [ ] Counter-evidence search executed for all high-materiality causal claims
- [ ] Verification uses distinct model from writer

### Phase 5 — Enterprise Governance
- [ ] Cross-tenant authorization tests pass
- [ ] Resume does not duplicate side effects
- [ ] Prompt injection cannot trigger unauthorized tools
- [ ] Audit events complete and chain-verified
- [ ] Credentials never enter model context

### Phase 6 — Continuous Research
- [ ] Saved research workflow updates prior findings without blind rebuild
- [ ] Source content changes detected and claims invalidated
- [ ] Research skills load through progressive disclosure
- [ ] Domain templates produce consistent outputs across runs

## Related Documents

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Full system architecture
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — Security threat analysis
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Phased implementation plan
- [`AGENTS.md`](AGENTS.md) — Code conventions
