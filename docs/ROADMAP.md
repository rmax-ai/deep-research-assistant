# Deep Research Assistant — Implementation Roadmap

**Document version:** 1.0.0
**Derived from:** Mega Specification v1.0, section 25

---

## Phase 0: Architecture Spike

**Focus:** ADK 2.0 workflow skeleton, one end-to-end demo

**Deliverables:**
- [ ] ADK 2.0 Workflow graph with deterministic nodes (scope → render)
- [ ] Session persistence (PostgreSQL or SQLite)
- [ ] Event streaming infrastructure
- [ ] Simple web search tool integration
- [ ] Source and claim data schemas (Pydantic models)
- [ ] One end-to-end demo: "analyze X" → structured output
- [ ] Interruption and resumption without duplicating completed stages

**Dependencies:** None (foundation)

**Estimated Codex sessions:** 3-4

**Exit criterion:** A research run can be interrupted and resumed without duplicating completed stages.

---

## Phase 1: Evidence-First MVP

**Focus:** Core research pipeline — scope through report with citations

**Deliverables:**
- [ ] Research Director Agent (scope interpretation)
- [ ] Perspective Planner Agent
- [ ] Question Architect Agent + question graph persistence
- [ ] Query Planner Agent + search plan execution
- [ ] Source record creation and storage
- [ ] Evidence Curator Agent + evidence extraction
- [ ] Claim Builder Agent + atomic claim creation
- [ ] Basic outline generation
- [ ] Section Writer Agent (prose from claims)
- [ ] Citation linking (report → claim → evidence → source)
- [ ] REST API surface (create, inspect, export)
- [ ] Local development deployment (ADK InMemoryRunner + SQLite)

**Excluded:**
- Advanced contradiction detection
- Collaborative UI
- Continuous watch mode
- Enterprise corpora (MCP integration)

**Dependencies:** Phase 0

**Estimated Codex sessions:** 8-10

**Exit criteria:**
- All substantive report claims map to claim records
- All source-derived claims map to evidence fragments
- Reports survive automated citation-entailment tests

---

## Phase 2: STORM-Grade Iterative Research

**Focus:** Evidence-conditioned follow-up questions, research frontier scheduling, information-gain metrics

**Deliverables:**
- [ ] Research Moderator Agent (stagnation detection, rebalancing)
- [ ] Evidence-conditioned follow-up question generation
- [ ] Research frontier scheduler with priority function
- [ ] Iterative stopping conditions (information gain, coverage, diversity)
- [ ] Perspective budget allocation and tracking
- [ ] Section-local evidence retrieval (not global context)
- [ ] Information-gain metrics (IG_t calculation)
- [ ] Semantic budget tracking

**Dependencies:** Phase 1

**Estimated Codex sessions:** 6-8

**Exit criterion:** Compute-matched evaluation demonstrates better coverage than one-shot RAG.

---

## Phase 3: Co-STORM-Style Collaboration

**Focus:** Live research frontier, user interventions, approval center

**Deliverables:**
- [ ] Streaming event infrastructure (UI events)
- [ ] Live research frontier projection
- [ ] Concept-map projection (from Knowledge Organizer graph)
- [ ] User intervention API and processing
- [ ] Question pinning / suppression
- [ ] Claim challenge workflow
- [ ] Mid-run scope changes
- [ ] Approval center (Gate A, B, C, D)
- [ ] Human-in-the-loop integration with ADK

**Dependencies:** Phase 2

**Estimated Codex sessions:** 8-10

**Exit criterion:** Users can steer a running investigation without corrupting workflow state.

---

## Phase 4: Epistemic Reliability

**Focus:** Contradiction detection, confidence model, independent verification

**Deliverables:**
- [ ] Counter-Evidence Agent (contradiction search)
- [ ] Contradiction graph persistence and resolution tracking
- [ ] Causal-claim review (explicit inference step validation)
- [ ] Source independence clustering (deterministic)
- [ ] Confidence model implementation (authority × independence × corroboration × freshness)
- [ ] Verification Agent with independence rule enforcement
- [ ] Cross-section consistency checks
- [ ] Citation entailment testing

**Dependencies:** Phase 2 (needs iterative research loop to exercise)

**Estimated Codex sessions:** 6-8

**Exit criterion:** Material unsupported-inference rate meets production threshold (<5%).

---

## Phase 5: Enterprise Governance

**Focus:** Identity, policy, MCP, audit, tenant isolation

**Deliverables:**
- [ ] Identity engine (principal context propagation)
- [ ] Policy engine (role-to-tool allowlists, stage-based reduction)
- [ ] MCP gateway (tool ingestion, normalization, risk classification)
- [ ] Source classification (public/internal/confidential/restricted)
- [ ] Human-gated writes (approval-enforced publication)
- [ ] Immutable audit log (append-only, chain-verified)
- [ ] Restricted-corpus support (tenant-scoped data access)
- [ ] Tenant isolation (RLS, tenant-prefixed storage)
- [ ] Governance dashboards (operational, quality, governance)
- [ ] Credential management (secret manager integration)
- [ ] Prompt-injection defenses (data/instruction channel separation)

**Dependencies:** Phase 3 (needs approval center), Phase 4 (needs verification)

**Estimated Codex sessions:** 10-12

**Exit criterion:** Security, authorization, and audit release gates pass (Phase 5 eval suite).

---

## Phase 6: Continuous Research and Reusable SOPs

**Focus:** Scheduled watches, reusable skills, knowledge publishing

**Deliverables:**
- [ ] Continuous watch mode (scheduled + delta detection)
- [ ] Source content change detection
- [ ] Claim invalidation on source changes
- [ ] Reusable research skills (SKILL.md with progressive disclosure)
- [ ] Domain templates (technical architecture, security analysis, standards review)
- [ ] ResearchSkillRegistry (internal abstraction over ADK skills)
- [ ] Organization-specific evidence policies
- [ ] Knowledge-layer publishing (validated claims → long-term memory)
- [ ] Research watch management API

**Dependencies:** Phase 5 (needs governance + audit)

**Estimated Codex sessions:** 6-8

**Exit criterion:** A saved research workflow can update prior findings without rebuilding the report blindly.

---

## Dependency Graph

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 5 ──► Phase 6
                         │            │            │
                         └──► Phase 4 ─┘────────────┘
```

- Phase 4 depends on Phase 2 (needs iterative loop) but can partially overlap with Phase 3
- Phase 5 depends on Phase 3 (approval center) and Phase 4 (verification)
- Phase 6 depends on Phase 5 (governance)

## Parallel Opportunities

- Phases 3 and 4 can run partially in parallel after Phase 2
- Phase 2 sub-components (Moderator, Scheduler, Stopping) are independently testable
- Phase 5 sub-components (Identity, Policy, Audit) are independently implementable

## Estimated Total Codex Sessions

| Phase | Sessions | Cumulative |
|-------|----------|------------|
| 0 | 3-4 | 4 |
| 1 | 8-10 | 14 |
| 2 | 6-8 | 22 |
| 3 | 8-10 | 32 |
| 4 | 6-8 | 40 |
| 5 | 10-12 | 52 |
| 6 | 6-8 | 60 |

**Total:** ~60 Codex sessions across all phases.

## Release Gates (Per Phase)

### Phase 1 Gate
- [ ] All substantive report claims map to claim records
- [ ] All source-derived claims map to evidence fragments
- [ ] Citation-entailment tests pass

### Phase 4 Gate
- [ ] No blocking security eval failures
- [ ] Unsupported material-claim rate < 5%
- [ ] Citation entailment > 90%
- [ ] Material inferred claims include explicit inference records

### Phase 5 Gate
- [ ] Cross-tenant authorization tests pass
- [ ] Resume behavior does not duplicate side effects
- [ ] Prompt injection cannot trigger unauthorized tools
- [ ] Audit events are complete and chain-verified

### Production Gate (Phase 6)
- [ ] High primary-source coverage (>50%)
- [ ] Traceable claim-level evidence
- [ ] Explicit uncertainty in all reports
- [ ] Counter-evidence coverage for material claims
- [ ] No blocking unsupported claims
- [ ] Stable resumable execution
- [ ] Enforced authorization boundaries
- [ ] Complete audit events
- [ ] Measurable cost and latency
- [ ] Successful human review
- [ ] Materially better decision usefulness than one-shot RAG baseline
