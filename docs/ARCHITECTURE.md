# Deep Research Assistant — System Architecture

**Document version:** 1.0.0  
**Derived from:** Mega Specification v1.0  
**Implementation target:** Google ADK 2.0, Python 3.12+  
**System class:** Stateful multi-agent research and synthesis assistant

---

## Executive Summary

The Deep Research Assistant is a governed research runtime built on Google ADK 2.0 that converts a broad research request into an inspectable, reproducible, evidence-backed research workflow. It implements a staged epistemic pipeline from intent through scope, perspectives, question graph, search plans, retrieved sources, evidence extraction, claim construction, contradiction analysis, coverage analysis, outline, section drafts, independent verification, human approval, to final report.

The system's fundamental unit of quality is not a polished paragraph. It is a **supported, qualified, and traceable claim.**

The architecture separates concerns across three planes: a **workflow plane** (deterministic graph orchestration), a **cognitive plane** (bounded LLM agents with narrow mandates), and a **governance plane** (identity, policy, audit, and human approval gates).

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       GOVERNANCE PLANE                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Identity  │  │ Policy   │  │ Approval │  │ Audit &          │ │
│  │ Engine    │  │ Engine   │  │ Center   │  │ Observability    │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────────┐
│                       WORKFLOW PLANE                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ADK 2.0 Workflow Graph                        │   │
│  │  scope → perspectives → questions → schedule → retrieve   │   │
│  │    → extract → claims → contradictions → coverage →       │   │
│  │    outline → draft → verify → render                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │Budget    │  │Stopping  │  │Checkpoint│  │ Retry &          │ │
│  │Manager   │  │Rules     │  │Manager   │  │ Recovery         │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────────┐
│                       COGNITIVE PLANE                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Research    │  │ Perspective  │  │ Question Architect     │  │
│  │ Director    │  │ Planner      │  │                        │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Moderator   │  │ Query        │  │ Source Appraiser       │  │
│  │             │  │ Planner      │  │                        │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Evidence    │  │ Claim        │  │ Counter-Evidence       │  │
│  │ Curator     │  │ Builder      │  │                        │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Outline     │  │ Section      │  │ Verifier               │  │
│  │ Architect   │  │ Writer       │  │                        │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│  ┌─────────────┐  ┌──────────────────────────────────────────┐  │
│  │ Knowledge   │  │ Executive Synthesizer                    │  │
│  │ Organizer   │  │                                          │  │
│  └─────────────┘  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Three-Plane Separation

| Plane | Responsibility | Examples |
|-------|---------------|----------|
| **Governance** | Identity, authorization, policy, approvals, audit | PolicyEngine, AuditStore, ApprovalGate |
| **Workflow** | Deterministic orchestration, scheduling, budgeting, persistence | ADK Workflow graph, BudgetManager, StoppingRules |
| **Cognitive** | Semantic interpretation, extraction, synthesis, verification | All 14 LlmAgents |

**Key rule:** Governance plane components are never LLM agents. Workflow plane uses deterministic code nodes where behavior can be specified precisely. Only the cognitive plane uses LLM agents.

---

## Component Architecture

### Workflow Topology (ADK 2.0 Graph)

```
START
  │
  ▼
SCOPE ─────────► [Scope + risk classification]
  │
  ▼
PERSPECTIVES ──► [Generate research perspectives]
  │
  ▼
QUESTIONS ─────► [Build initial question graph]
  │
  ▼
APPROVE_PLAN ──► {Plan approval gate}
  │ approved
  ▼
SCHEDULER ─────► [Research frontier scheduler]
  │
  ├──► SEARCH_PLAN ──► [Create search plan]
  │         │
  │         ▼
  │    RETRIEVE ──────► [Retrieve sources]
  │         │
  │         ▼
  │    SOURCE_POLICY ─► [Apply source policy filter]
  │         │
  │         ▼
  │    EXTRACT ───────► [Extract evidence fragments]
  │         │
  │         ▼
  │    CLAIMS ────────► [Construct or update claims]
  │         │
  │         ▼
  │    CONTRADICTIONS► [Search contradictions]
  │         │
  │         ▼
  │    COVERAGE ──────► [Calculate coverage + info gain]
  │         │
  │         ▼
  │    STOP ──────────► {Stop condition evaluation}
  │         │ continue → SCHEDULER
  │         │ sufficient ↓
  │         ▼
  OUTLINE ────────────► [Build typed outline]
  │
  ▼
APPROVE_OUTLINE ─────► {Outline approval gate}
  │ approved
  ▼
DRAFT ───────────────► [Generate section drafts]
  │
  ▼
VERIFY ──────────────► [Independent verification]
  │ material failures → REPAIR → VERIFY
  │ passed ↓
  ▼
FINAL_GATE ──────────► {Publication approval gate}
  │ approved
  ▼
RENDER ──────────────► [Render final outputs]
  │
  ▼
END
```

### Node Taxonomy

**Deterministic code nodes** (no LLM):
- Schema validation, policy lookup, source canonicalization
- Deduplication, independence clustering, budget accounting
- Priority scoring, graph persistence, citation rendering
- Approval routing, PII classification, content hashing
- Retry classification, metric calculation, stopping-rule evaluation

**LLM-backed nodes** (cognitive plane agents):
- Scope interpretation, perspective discovery, question generation
- Query decomposition, evidence extraction, atomic claim generation
- Inference classification, contradiction explanation, outline synthesis
- Prose generation, semantic verification

**Hybrid nodes** (deterministic + LLM):
- Source authority appraisal, source relevance ranking
- Claim confidence scoring, coverage analysis
- Information-gain estimation, repair planning

---

## Agent Roster (14 Agents)

### 1. Research Director Agent
- **Input:** User objective, constraints
- **Output:** `ResearchPlanProposal` (scope, perspectives, completion criteria, budget, approval recommendation)
- **Prohibited:** Browsing sources, writing prose, self-approval, modifying evidence
- **Model tier:** Reasoning

### 2. Perspective Planner Agent
- **Input:** Research scope, domain templates
- **Output:** List of `Perspective` definitions with non-overlapping coverage
- **Process:** Load templates → generate candidates → calculate semantic overlap → merge redundant → add policy-mandated perspectives
- **Mandatory defaults:** foundational, implementation/architecture, limitations/failure-modes, skeptical counter-analysis, enterprise implications

### 3. Question Architect Agent
- **Input:** Perspectives, scope, objective
- **Output:** Initial `QuestionGraph` (questions with dependencies, types, priorities)
- **Mixture required:** Foundational, architecture, evidence, failure-mode, counter-evidence, enterprise-impact questions
- **Prohibited:** Generating prose answers to its own questions

### 4. Research Moderator Agent (Co-STORM-inspired)
- **Input:** Current research frontier, frontier metrics
- **Triggers:** Low-novelty cycles, single-cluster evidence dominance, missing adversarial evidence, unresolved high-risk questions, perspective imbalance, user challenges
- **Output:** Intervention decisions (introduce questions, rebalance, reopen)

### 5. Query Planner Agent
- **Input:** Single `ResearchQuestion`
- **Output:** `SearchPlan` with multiple query strategies
- **Strategies:** Exact terminology, synonyms, official docs, standards, repository/issue search, academic, failure/incident, comparative, counterclaim, date-constrained

### 6. Source Appraiser Agent
- **Input:** Source metadata, claim context
- **Output:** Authority classification (claim-relative), trust score, freshness score, policy recommendation
- **Claim-relative rule:** A vendor doc is high-authority for its API, medium for architecture, low for comparative superiority

### 7. Evidence Curator Agent
- **Input:** Source content, relevant passages
- **Output:** `EvidenceFragment` (exact excerpt, normalized statement, qualifiers, temporal scope)
- **Prohibited:** Creating cross-source conclusions, replacing text with summary
- **Immutable rule:** Exact excerpts must never be modified after extraction

### 8. Claim Builder Agent
- **Input:** Evidence fragments, existing claims, inference context
- **Output:** `Claim` objects with epistemic status, evidence links, inference steps
- **Atomicity rule:** One subject, one predicate, one principal qualification per claim
- **Model tier:** Reasoning

### 9. Counter-Evidence Agent
- **Input:** Material claims (especially inferred/causal), source graph
- **Output:** Contradiction records, counter-evidence fragments
- **Required for:** Every high-materiality inferred or causal claim
- **Searches for:** Failed implementations, retractions, alternative explanations, non-independent sources

### 10. Knowledge Organizer Agent
- **Input:** Questions, claims, evidence, contradictions
- **Output:** Conceptual hierarchy with multi-parent support, version history
- **Responsibility:** Maintain the underlying graph that the UI "mind map" projects

### 11. Outline Architect Agent
- **Input:** Validated claims, contradictions, unresolved questions, audience, output template
- **Output:** `Outline` with sections, claim assignments, evidence requirements
- **Rejection rule:** Outline rejected if material section lacks sufficient evidence

### 12. Section Writer Agent
- **Input:** Section purpose, approved claim IDs, allowed evidence, glossary, style
- **Output:** Section draft (or `blocked` status with missing claims)
- **Prohibited:** Introducing new substantive claims, independent browsing
- **Model tier:** Reasoning

### 13. Verification Agent
- **Input:** Section drafts, approved claims, evidence registry
- **Output:** `VerificationFinding` list (blocking/major/minor/stylistic)
- **Passes:** Proposition extraction, claim-registry matching, evidence entailment, citation completeness, qualifier preservation, relationship validation, contradiction consistency, cross-section consistency, temporal consistency
- **Independence rule:** Must use distinct model family or configuration from the writer

### 14. Executive Synthesizer Agent
- **Input:** Verified report, claims, contradictions, decision context
- **Output:** Executive synthesis with confidence indicators
- **Gate:** Can only run after verification passes

---

## Core Data Model

### ResearchRun (Aggregate Root)

```
ResearchRun
├── ResearchObjective (title, primary_question, decision_to_support, audience, output_type, depth, deadline)
├── ResearchScope (included/excluded topics, dimensions, jurisdictions, time_range, source_constraints, definitions, assumptions, risk_level)
├── List[Perspective] (id, name, purpose, required_questions, preferred_source_types, required_checks, prohibited_actions, budget_weight)
├── List[ResearchQuestion] (id, text, type, perspective_id, parent/child IDs, origin, rationale, priority, novelty_score, risk_score, status, resolution_summary)
├── List[SearchPlan] (question_id, objective, queries, source_mix, exclusion_rules, freshness, max_results, stop_conditions)
├── List[SourceRecord] (source_id, canonical_uri, publisher, author, date, source_type, authority_class, independence_cluster_id, content_hash, trust_score, freshness_score, policy_status)
├── List[EvidenceFragment] (evidence_id, source_id, locator, exact_excerpt, normalized_statement, surrounding_context, extraction_method, evidence_type, temporal_scope, qualifiers, confidence, content_hash)
├── List[Claim] (claim_id, text, atomic_form, claim_type, epistemic_status, evidence_ids, supporting/contradicting claims, inference_steps, qualifiers, confidence, materiality, review_status, owner_agent)
├── List[Contradiction] (contradiction_id, claim_ids, type, explanation, possible_resolution, resolution_status, materiality)
├── List[Outline] (versioned, sections with required_claim_ids, unresolved_question_ids, evidence_requirements)
├── List[SectionDraft] (section_id, content, status, blocked_reason, missing_claims)
├── List[VerificationFinding] (severity, description, affected_claims)
├── List[ApprovalDecision] (approval_id, gate, decision, rationale, timestamp, approver)
└── ResearchMetrics (coverage scores, contradiction rates, source diversity, cost, latency)
```

### Epistemic Status Taxonomy

Claims carry one of:
- `source-stated` — directly from a source
- `directly-observed` — from tool execution
- `extracted` — derived from source content by LLM
- `corroborated` — supported by multiple independent sources
- `inferred` — synthesized across sources
- `causal-inference` — claims about causation
- `disputed` — challenged by counter-evidence
- `speculative` — insufficient support
- `recommendation` — prescriptive, inherits uncertainty from supporting claims
- `unresolved` — pending further investigation

### Question Type Taxonomy

| Type | Example |
|------|---------|
| definitional | "What is a tool execution sandbox?" |
| descriptive | "How does ADK handle session state?" |
| mechanistic | "How does the before_model_callback short-circuit work?" |
| comparative | "How does ADK tool governance compare to MCP?" |
| historical | "Why was SequentialAgent deprecated in ADK v2?" |
| causal | "Does prompt-injection scanning reduce exfiltration risk?" |
| normative | "Should a verifier use the same model as the writer?" |
| quantitative | "What is the unsupported-claim rate at Phase 4?" |
| implementation | "How to implement identity propagation in ADK tools?" |
| security | "Can delegated scopes expand without detection?" |
| failure-mode | "What happens when Gemini structured output fails?" |
| counterfactual | "What if we didn't have a contradiction agent?" |
| evidence-challenge | "Is this source actually independent?" |
| contradiction-resolution | "Why do source A and source B disagree?" |

---

## Trust Boundaries

| Boundary | What It Protects | Enforcement |
|----------|-----------------|-------------|
| **TB-1: Tool invocation** | Agents cannot call tools outside role- and stage-bound allowlists | Policy engine at tool dispatch |
| **TB-2: Identity propagation** | Every tool call carries full principal context (tenant, user, run, agent, purpose) | Identity engine at each node |
| **TB-3: Evidence immutability** | Exact excerpts never modified after extraction | Content hashing + append-only storage |
| **TB-4: Retrieval instructions** | Source content cannot issue instructions to agents | Prompt-injection isolation (data/instruction channel separation) |
| **TB-5: Write authorization** | Controlled writes require explicit policy + user confirmation | Approval gate before write dispatch |
| **TB-6: Verification independence** | Verifier cannot share writer's model, prompt, temperature, or context framing | Model routing policy enforcement |
| **TB-7: Audit immutability** | Audit events append-only, unmodifiable by workflow agents | Separate audit storage, no agent write access |
| **TB-8: Credential isolation** | Credentials never enter model context, never propagate across unauthorized boundaries | Secret manager integration, credential-use logging |
| **TB-9: Cross-tenant isolation** | One tenant's research cannot leak into another's | Tenant-scoped storage, queries, and model contexts |
| **TB-10: Source quarantine** | Sources flagged for prompt injection or policy violation isolated from model consumption | Source policy engine with quarantine bucket |

---

## Policy Model

### Dimensions
- **Identity dimension:** Who is acting? (tenant, user, agent role, workflow instance)
- **Purpose dimension:** Why? (run objective, current stage, intended output)
- **Scope dimension:** What boundaries? (source restrictions, topic exclusions, time range)
- **Risk dimension:** How sensitive? (risk_level from scope classification)
- **Budget dimension:** How much? (searches, tokens, cost, wall-time)

### Evaluation Order
1. Identity lookup → resolved principal
2. Role-to-tool allowlist check
3. Stage-to-tool allowlist check
4. Purpose-expansion detection
5. Budget remaining check
6. Risk-based confirmation requirement
7. Source-domain allowlist/blocklist
8. Prompt-injection scan (for retrieved content)

### Assignment Hierarchy
- **Workflow-configured:** Agent role → allowed tools per stage
- **Run-configured:** User/scope constraints → source restrictions
- **Policy-configured:** Organization-wide rules → minimum primary source ratio, mandatory counter-searches
- **Dynamic:** Risk classification → approval gate requirements

---

## Credential Model

### Principles
1. Credentials live outside prompts and model context
2. Short-lived credentials where supported (workload identity)
3. User-delegated OAuth for user-owned systems
4. Secret manager integration (not env vars for secrets)
5. Credential use logged without logging secrets
6. No credential propagation across unauthorized subagents

### Credential Injection Points
- **MCP servers:** OAuth tokens or workload identity
- **Web search tools:** API keys from secret manager
- **Enterprise search:** User-delegated OAuth
- **Source snapshot storage:** Workload identity to object storage
- **Model providers:** Service account or API key from secret manager

---

## Tool Governance

### Classification
| Class | Examples | Write? | Confirmation? |
|-------|----------|--------|---------------|
| Read-only research | web_search, url_retrieve, academic_search, standards_search, repository_search | No | No |
| Analytical | embedding_similarity, deduplication, independence_clustering, citation_entailment, code_execution_sandbox | No (internal) | No |
| Controlled write | save_artifact, create_draft, publish_internal, update_watch, write_knowledge_record | Yes | Policy-dependent |
| Publication | publish_external, send_to_third_party | Yes | Always |

### Tool Selection Policy (Dynamic Reduction)
Tool visibility reduces dynamically by:
- Workflow stage (section writer doesn't see search tools)
- Agent role (evidence curator sees extraction tools, not publication tools)
- User identity (tenant-restricted corpora only visible to authorized users)
- Risk classification (high-risk runs disable automatic writes)
- Budget remaining (expensive tools disabled when budget exhausted)

### MCP Integration Requirements
- Explicit allowlisting (no auto-discovery of tools)
- Tool metadata normalization
- Read/write classification
- Risk tier assignment
- OAuth or workload identity
- Per-user authorization
- Timeout and retry policy
- Schema validation
- Output-size limits
- Audit logging
- Prompt-injection scanning
- Confirmation policy

---

## Workflow Engine

### Capabilities
- **Graph execution:** ADK 2.0 Workflow with 14+ nodes
- **Parallelism:** Independent questions execute concurrently (configurable max)
- **Checkpointing:** After plan completion, each research batch, claim-graph update, outline generation, each section draft, verification pass, approval decision
- **Idempotency:** Every node uses `run_id + node_path + logical_input_hash + workflow_version` as idempotency key
- **Retry:** Transient failures only (rate limits, network, provider unavailability, retriable model errors)
- **No retry:** Auth denial, policy rejection, schema invalidity, prohibited source, user rejection, budget exhaustion
- **Resumption:** On interruption, persists current graph node, active branches, partial outputs, budget state, pending confirmations, retry count, model/tool versions

### Research Frontier Scheduler Priority Function

```
Priority(q) = w_m * M(q) + w_r * R(q) + w_d * D(q) + w_u * U(q) + w_n * N(q) - w_c * C(q)
```

Where:
- M = materiality
- R = risk
- D = dependency centrality
- U = uncertainty
- N = expected novelty
- C = expected cost

### Stopping Decision

```python
class StoppingDecision:
    should_stop: bool
    reasons: list[str]
    unresolved_material_questions: list[str]
    marginal_information_gain: float
    evidence_diversity_score: float
    primary_source_coverage: float
    contradiction_resolution_rate: float
    budget_remaining: ResearchBudget
```

### Information Gain Approximation

```
IG_t = α·N_c + β·N_e + γ·N_k + δ·C_r - λ·D
```

Where:
- N_c = novel supported claims
- N_e = novel independent evidence
- N_k = newly resolved knowledge gaps
- C_r = contradictions resolved
- D = duplicated/redundant evidence

Stop when moving average of IG_t falls below threshold AND all material coverage constraints are satisfied.

---

## Approval System

### Approval Gates

| Gate | Trigger Condition | Display |
|------|------------------|---------|
| **Gate A: Scope** | High-risk subject, ambiguous request, restricted corpora, budget exceeds policy | Research objective, scope, risk level |
| **Gate B: Research Plan** | After question graph generation | Perspectives, questions, source strategy, estimated budget, exclusions, limitations |
| **Gate C: Evidence & Outline** | After coverage check, before drafting | Principal claims, confidence, source mix, contradictions, unresolved questions, proposed outline |
| **Gate D: Recommendation** | Security decisions, legal/regulatory, material financial, external publication, production changes | Final claims, recommendations, risk indicators |

### User Interventions (Collaborative Mode)

Supported commands during a running investigation:
- "Investigate this question." / "Stop researching this branch."
- "Only use primary sources." / "Exclude vendor-authored evidence."
- "Challenge claim C-142." / "Explain why this source was trusted."
- "Show unresolved contradictions." / "Increase depth on security."
- "Generate the report now." / "Resume the run."
- "Compare against a new alternative."

Every intervention becomes an auditable event.

---

## Inference Gateway (Model Routing)

### Routing Dimensions
- Operation type
- Risk level
- Required context size
- Output schema difficulty
- Latency requirements
- Cost constraints
- Multilingual requirements
- Citation sensitivity
- Verification independence

### Model Tiers

| Tier | Use Cases | Latency Budget |
|------|-----------|---------------|
| **Fast** | Query expansion, classification, deduplication, low-risk extraction, tool output summarization | <5s |
| **Reasoning** | Scope construction, question planning, claim inference, contradiction analysis, outline construction, architecture synthesis | <30s |
| **Verification** | Claim entailment, causal-overreach detection, high-risk review, final recommendation validation | <60s |

### Independence Rule
For high-materiality content, the verifier MUST use:
- A distinct model family, OR
- A separately configured model instance (different prompt, temperature, context framing), OR
- Deterministic checks combined with model review

**Never:** Same model + same prompt + same temperature for writer and verifier on material claims.

---

## Knowledge and Memory Layer

### Storage Architecture

| Store | Technology | Purpose |
|-------|-----------|---------|
| **Core state** | PostgreSQL / Cloud SQL | Transactional run state, claims, evidence, contradictions |
| **Graph relationships** | PostgreSQL (or optional graph DB) | Question graph, claim-evidence graph, conceptual hierarchy |
| **Source snapshots** | Object storage (GCS/S3) | Immutable source content, versioned |
| **Artifacts** | Object storage | Reports, diagrams, evidence packages |
| **Vector index** | Vector DB (e.g. pgvector) | Semantic search over questions, claims, evidence |
| **Audit log** | Append-only table | All governance events |
| **Analytics** | Analytics warehouse | Cost, latency, quality metrics for dashboards |

### Session State vs Durable State

| What | Where | Lifetime |
|------|-------|----------|
| Active run context | Session state | Current interaction |
| Pending approvals | Session state | Until resolved |
| User preferences (run-scoped) | Session state | Duration of run |
| Evidence corpus | Durable DB | Run lifetime + retention |
| Claim graph | Durable DB | Run lifetime + retention |
| Source snapshots | Object storage | Configurable retention |
| Generated artifacts | Object storage | Configurable retention |
| Audit events | Audit DB | Permanent |

**Critical rule:** The complete evidence corpus must NOT be placed in session state.

### Long-Term Memory

Long-term memory may contain:
- Approved research templates
- User-approved preferences
- Domain glossaries
- Prior validated claims
- Prior source authority decisions
- Known failed query patterns

**Crucially:** Remembered claims do NOT enter a new run as current evidence. They enter as **hypotheses requiring freshness checks.**

---

## Observability and Audit

### Trace Model
Every node span records: run_id, workflow_version, node_path, agent_name, model_name, prompt_version, tool_name, input/output hashes, latency, token usage, cost, retry_count, policy_decision, error_classification.

### Audit Events (Append-Only)
- run.created, scope.changed, skill.loaded
- question.created, query.executed, source.retrieved
- policy.decision, evidence.extracted, claim.created
- inference.created, contradiction.recorded
- approval.requested, approval.decided
- model.invocation, tool.invocation
- budget.exceeded, report.generated, report.published

### Dashboards

**Operational:** Run success rate, node latency, provider errors, retries, cost, queue depth, interruption rate.

**Research Quality:** Unsupported-claim rate, primary-source ratio, citation entailment, contradiction coverage, source independence, human correction rate, report acceptance rate.

**Governance:** Restricted-source access, approval bypass attempts, policy denials, prompt-injection detections, publication events, data-classification violations.

---

## API and Data Model

### REST API Surface
- `POST /v1/research-runs` — Create run
- `GET /v1/research-runs/{run_id}` — Inspect run
- `GET /v1/research-runs/{run_id}/graph` — Get research graph
- `POST /v1/research-runs/{run_id}/interventions` — User intervention
- `POST /v1/research-runs/{run_id}/approvals/{approval_id}` — Approve/reject gate
- `POST /v1/research-runs/{run_id}:resume` — Resume interrupted run
- `POST /v1/research-runs/{run_id}/exports` — Export (formats: markdown, HTML, PDF, JSON, evidence package, executive brief)

### Streaming Events
- `run.started`, `scope.proposed`, `approval.requested`
- `perspective.created`, `question.created`
- `query.executed`, `source.accepted`
- `evidence.extracted`, `claim.created`
- `contradiction.detected`, `coverage.updated`
- `outline.proposed`, `section.generated`
- `verification.failed`, `verification.passed`
- `run.completed`

---

## Deployment Topology

### Local Development
- ADK 2.0 InMemoryRunner + InMemorySessionService
- SQLite for core state
- Local file storage for artifacts
- Single-tenant, no auth

### Single-Tenant Cloud Run
- ADK 2.0 with Cloud Run agent runtime
- Cloud SQL (PostgreSQL) for core state
- GCS for source snapshots and artifacts
- Workload identity for service-to-service auth
- Full governance stack (identity, policy, audit)

### Multi-Tenant GKE
- ADK 2.0 on GKE with agent runtime
- Cloud SQL with tenant-scoped schemas or row-level security
- GCS with tenant-prefixed buckets
- Full governance with tenant isolation
- Horizontal scaling per tenant

### Air-Gapped
- Self-hosted ADK runtime
- Local PostgreSQL
- MinIO or local filesystem for artifacts
- No external model providers (local inference)
- Full governance (all controls local)

---

## Configuration Model

```yaml
application:
  name: deep-research-assistant
  environment: production

workflow:
  version: 1.0.0
  maximum_parallel_questions: 6
  checkpoint_after_each_batch: true
  verification_repair_limit: 2

models:
  fast:
    provider: google
    model: configured-fast-model
  reasoning:
    provider: google
    model: configured-reasoning-model
  verification:
    provider: google
    model: configured-verification-model

research_policy:
  minimum_primary_source_ratio: 0.5
  required_counter_search_materiality: high
  maximum_source_age_days: null
  require_source_snapshots: true
  allow_vendor_sources: true
  vendor_claims_require_independent_support: true

security:
  enforce_identity_propagation: true
  require_confirmation_for_writes: true
  quarantine_untrusted_instructions: true

budgets:
  default:
    searches: 80
    opened_sources: 50
    maximum_cost: 25
    maximum_wall_time_seconds: 1800

approvals:
  scope:
    required_for_risk: high
  outline:
    required_for_risk: high
  publication:
    required_for_external: true
```

---

## Risks, Trade-offs, and Open Questions

### Key Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Excessive orchestration complexity | Debug difficulty, long dev cycles | Prefer deterministic nodes; use agents only for semantic work; keep schemas stable; develop workflow visualizations |
| Cost growth | Unsustainable at scale | Semantic stopping rules; model routing; query deduplication; evidence reuse; parallelism limits; cost-per-claim metrics |
| False confidence from citations | Undetected errors in reports | Atomic claims; entailment verification; source authority assessment; explicit inference tracking; contradiction searches |
| Dialogue-state contamination | Claims without evidence backing | Persist structured objects; keep transcripts secondary; prevent answers from becoming evidence; require evidence links |
| Skill API instability (ADK) | Breakage on ADK upgrades | Internal skill abstraction; version pinning; contract tests; fallback static instructions |
| Retrieval prompt injection | Tool hijacking via source content | Untrusted-content isolation; tool restrictions; source quarantine; schema-based outputs; security evals |
| Graph explosion | Performance degradation | Graph compaction; question deduplication; archival of low-value branches; summary projections; configurable retention |
| Gemini structured output reliability | Malformed JSON from response_schema | Text-based fallback patterns; simple schemas only; dual-path with retry |
| ADK v2 deprecation of SequentialAgent/ParallelAgent/LoopAgent | Must use Workflow graph | Architecture assumed from start; no legacy migration needed |
| ADK v2.2.0 InMemoryRunner constructor change | No session_service= param | Use InMemoryRunner(agent=..., app_name=...) directly |

### Open Questions
1. **Graph DB necessity:** Do we need a dedicated graph database for the question/claim/evidence graph, or is PostgreSQL with recursive CTEs sufficient for Phase 3+?
2. **UI framework:** The spec defines UI panes (section 22) but not a technology choice. Streamlit for MVP, or something richer?
3. **MCP provider selection:** Which MCP servers for enterprise search, GitHub, standards? Need concrete provider evaluation.
4. **Evaluation harness:** Golden dataset format is defined but actual dataset creation is out of scope until Phase 2+.
5. **Gemini rate limits:** How many concurrent Gemini requests does the Google Cloud quota actually permit? The spec assumes parallelism but ADK v2 research shows serialization.
