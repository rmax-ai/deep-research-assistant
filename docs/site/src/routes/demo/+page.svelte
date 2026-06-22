<script>
  import { base } from "$app/paths";

  const sampleForm = {
    apiBase: "http://localhost:8080/v1",
    title: "ADK tool governance deep research demo",
    primaryQuestion:
      "How should a Google ADK-based research assistant govern tool usage safely in an enterprise environment?",
    decisionToSupport: "Choose runtime guardrails for production rollout",
    tenantId: "demo",
    userId: "architect-01",
    mode: "review_first",
    existingRunId: "071521de"
  };
  const modeOptions = [
    { value: "autonomous", label: "Autonomous" },
    { value: "collaborative", label: "Collaborative" },
    { value: "review_first", label: "Review first" },
    { value: "continuous_watch", label: "Continuous watch" }
  ];

  const sampleSummary = {
    runId: "071521de",
    status: "awaiting_approval",
    phase: "awaiting_approval",
    questions: 14,
    claims: 8,
    sources: 11,
    title: "ADK tool governance deep research demo",
    primaryQuestion:
      "How should a Google ADK-based research assistant govern tool usage safely in an enterprise environment?",
    reportPreview:
      "Preliminary findings indicate that tool governance should combine identity propagation, bounded tool access, approval gates for external writes, and durable audit trails."
  };

  const sampleEvents = [
    {
      event_type: "approval.requested",
      timestamp: "Jun 22, 10:11:42",
      summary: "Scope proposal paused for gate A approval",
      payload: {
        gate: "A",
        required: true,
        risk_level: "high",
        message: "Scope proposal requires human approval before continuing."
      }
    },
    {
      event_type: "question.created",
      timestamp: "Jun 22, 10:11:08",
      summary: "Question graph version 2 created for governance and risk framing",
      payload: {
        questions_version: 2,
        count: 14,
        perspective: "governance"
      }
    },
    {
      event_type: "source.accepted",
      timestamp: "Jun 22, 10:10:41",
      summary: "Accepted primary source for policy and audit requirements",
      payload: {
        source_id: "src-013",
        title: "Enterprise agent governance controls",
        source_type: "primary"
      }
    },
    {
      event_type: "node.completed",
      timestamp: "Jun 22, 10:10:17",
      summary: "Completed perspective generation",
      payload: {
        node_name: "perspective_generate",
        duration_ms: 891
      }
    }
  ];

  const sampleApprovals = [
    {
      id: "A",
      gate: "Scope review",
      status: "pending",
      rationale: "Awaiting human confirmation that the risk framing and exclusions are appropriate."
    },
    {
      id: "B",
      gate: "Research plan",
      status: "not_required",
      rationale: "This gate has not been reached yet in the current snapshot."
    }
  ];

  const sampleClaims = [
    "High-risk tool categories need explicit human approval gates before external side effects.",
    "Identity propagation should be attached to every tool call for policy and audit enforcement.",
    "Append-only audit logs materially improve post-run reviewability for enterprise adoption."
  ];

  const sampleSources = [
    "Enterprise agent governance controls",
    "Internal platform guardrail policy v2",
    "Model tool access review checklist"
  ];

  const sampleConceptNodes = [
    { label: "Governance", type: "perspective" },
    { label: "Approval Gate Design", type: "concept" },
    { label: "Audit and Traceability", type: "concept" },
    { label: "Policy Enforcement", type: "concept" }
  ];

  const sampleLogs = [
    {
      level: "INFO",
      timestamp: "Jun 22, 10:11:42",
      message: "approval requested for gate A",
      record: {
        level: "INFO",
        logger: "deep_research.workflow.graph",
        message: "approval requested for gate A",
        run_id: "071521de",
        phase: "awaiting_approval"
      }
    },
    {
      level: "INFO",
      timestamp: "Jun 22, 10:11:08",
      message: "question graph version 2 committed",
      record: {
        level: "INFO",
        logger: "deep_research.workflow.graph",
        message: "question graph version 2 committed",
        run_id: "071521de",
        question_count: 14
      }
    }
  ];

  const sampleExport = `# ADK tool governance deep research demo

## Executive summary

The current snapshot suggests a production research runtime should separate read-only retrieval from write-capable tools, require human approval for high-risk external actions, and carry principal identity through every workflow node.

## Working recommendations

1. Preserve identity context on every tool invocation.
2. Enforce explicit approval gates for external side effects.
3. Keep evidence, claims, and audit events independently inspectable.
4. Prefer durable checkpoints so interrupted runs can resume safely.`;

  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }
</script>

<svelte:head>
  <title>Demo Snapshot · Deep Research Assistant</title>
  <meta
    name="description"
    content="Static snapshot of the Deep Research Assistant demo UI showing the standalone frontend design and operator-facing workflow panels."
  />
</svelte:head>

<section class="demo-shell">
  <div class="notice-band">
    <span class="notice-label">Snapshot Only</span>
    <div>
      <strong>This docs page is a non-interactive snapshot of the demo UI system.</strong>
      <p>
        Inputs and buttons are intentionally disabled here. Run the standalone demo locally from
        <code>docs/demo</code> to create or attach to real research runs against a live API
        instance.
      </p>
      <p class="notice-actions">
        <a href={base + "/api/"}>Read the API reference</a>
        <span>·</span>
        <code>cd docs/demo && npm install && npm run dev</code>
      </p>
    </div>
  </div>

  <header class="hero">
    <div class="hero-copy">
      <div class="eyebrow">Standalone demo preview</div>
      <h1>See the research-run cockpit before you run it locally.</h1>
      <p class="lede">
        This page mirrors the standalone demo layout: run creation, current status, live workflow
        timeline, approvals, graph summaries, logs, and export preview.
      </p>
    </div>

    <div class="hero-note">
      <span>Snapshot target</span>
      <strong><code>{sampleForm.apiBase}</code></strong>
      <p>The real standalone demo persists URL state and connects directly to your running API server.</p>
    </div>
  </header>

  <section class="control-grid" aria-label="Run controls and status">
    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Create run</span>
          <h2>Research run request</h2>
        </div>
        <span class="pill">POST /v1/research-runs</span>
      </div>

      <form class="run-form" on:submit|preventDefault>
        <label>
          <span>API Base URL</span>
          <input value={sampleForm.apiBase} disabled />
        </label>

        <label>
          <span>Title</span>
          <input value={sampleForm.title} disabled />
        </label>

        <label>
          <span>Primary question</span>
          <textarea rows="4" disabled>{sampleForm.primaryQuestion}</textarea>
        </label>

        <label>
          <span>Decision to support</span>
          <textarea rows="3" disabled>{sampleForm.decisionToSupport}</textarea>
        </label>

        <div class="form-row">
          <label>
            <span>Tenant ID</span>
            <input value={sampleForm.tenantId} disabled />
          </label>

          <label>
            <span>User ID</span>
            <input value={sampleForm.userId} disabled />
          </label>
        </div>

        <label>
          <span>Mode</span>
          <select value={sampleForm.mode} disabled>
            {#each modeOptions as option}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
        </label>

        <div class="form-actions">
          <button class="btn primary" type="button" disabled>Start research run</button>
          <button class="btn secondary" type="button" disabled>Reset defaults</button>
        </div>

        <div class="divider">
          <span>or</span>
        </div>

        <div class="load-run">
          <label>
            <span>Existing Run ID</span>
            <input value={sampleForm.existingRunId} disabled />
          </label>

          <button class="btn tertiary" type="button" disabled>Load existing run</button>
        </div>
      </form>
    </article>

    <article class="panel summary-panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Current run</span>
          <h2>Live status summary</h2>
        </div>
        <span class="pill stream-connected">SSE connected</span>
      </div>

      <div class="summary-stack">
        <div class="summary-topline">
          <div>
            <span class="meta-label">Run ID</span>
            <strong class="run-id">{sampleSummary.runId}</strong>
          </div>
          <span class={`status status-${sampleSummary.status}`}>{sampleSummary.status}</span>
        </div>

        <div class="metrics-grid">
          <div class="metric">
            <span>Phase</span>
            <strong>{sampleSummary.phase}</strong>
          </div>
          <div class="metric">
            <span>Questions</span>
            <strong>{sampleSummary.questions}</strong>
          </div>
          <div class="metric">
            <span>Claims</span>
            <strong>{sampleSummary.claims}</strong>
          </div>
          <div class="metric">
            <span>Sources</span>
            <strong>{sampleSummary.sources}</strong>
          </div>
        </div>

        <div class="summary-copy">
          <div>
            <span class="meta-label">Title</span>
            <p>{sampleSummary.title}</p>
          </div>

          <div>
            <span class="meta-label">Primary question</span>
            <p>{sampleSummary.primaryQuestion}</p>
          </div>

          <div>
            <span class="meta-label">Report preview</span>
            <p>{sampleSummary.reportPreview}</p>
          </div>
        </div>

        <div class="summary-foot">
          <p class="notice">Polling every 3s</p>
          <p class="notice warn">Run paused for approval. This snapshot shows the operator review state.</p>
        </div>
      </div>
    </article>
  </section>

  <section class="timeline-panel">
    <div class="panel-header timeline-header">
      <div>
        <span class="kicker">Timeline</span>
        <h2>Live workflow events</h2>
      </div>
      <span class="pill">{sampleEvents.length} events</span>
    </div>

    <div class="timeline-list">
      {#each sampleEvents as eventRecord}
        <article class="timeline-item">
          <div class="timeline-meta">
            <span class="event-type">{eventRecord.event_type}</span>
            <span>{eventRecord.timestamp}</span>
          </div>
          <p>{eventRecord.summary}</p>
          <details>
            <summary>Payload</summary>
            <pre>{formatJson(eventRecord.payload)}</pre>
          </details>
        </article>
      {/each}
    </div>
  </section>

  <section class="inspector-grid" aria-label="Snapshot run inspection panels">
    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Approvals</span>
          <h2>Gate decisions</h2>
        </div>
        <button class="btn tertiary" type="button" disabled>Refresh panels</button>
      </div>

      <div class="stack">
        <label>
          <span>Shared rationale</span>
          <textarea rows="3" disabled>
Proceed with the scope proposal if the exclusions and external write controls remain explicit.
          </textarea>
        </label>

        <div class="approval-list">
          {#each sampleApprovals as approval}
            <article class="approval-card">
              <div class="approval-header">
                <div>
                  <span class="meta-label">Gate {approval.id}</span>
                  <p class="approval-title">{approval.gate}</p>
                </div>
                <span class={`status status-${approval.status}`}>{approval.status}</span>
              </div>

              <p class:muted={!approval.rationale}>{approval.rationale}</p>

              {#if approval.status === "pending"}
                <div class="action-row">
                  <button class="btn secondary compact" type="button" disabled>approved</button>
                  <button class="btn secondary compact" type="button" disabled>rejected</button>
                </div>
              {/if}
            </article>
          {/each}
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Research graph</span>
          <h2>Claims and sources</h2>
        </div>
        <span class="pill">{sampleClaims.length + sampleSources.length} records</span>
      </div>

      <div class="stack">
        <div class="mini-metrics">
          <div class="mini-metric">
            <span>Claims</span>
            <strong>{sampleClaims.length}</strong>
          </div>
          <div class="mini-metric">
            <span>Sources</span>
            <strong>{sampleSources.length}</strong>
          </div>
        </div>

        <div class="list-block">
          <span class="meta-label">Recent claims</span>
          <ul class="plain-list">
            {#each sampleClaims as claim}
              <li>{claim}</li>
            {/each}
          </ul>
        </div>

        <div class="list-block">
          <span class="meta-label">Recent sources</span>
          <ul class="plain-list">
            {#each sampleSources as source}
              <li>{source}</li>
            {/each}
          </ul>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Concept map</span>
          <h2>Topic projection</h2>
        </div>
        <span class="pill">1 version</span>
      </div>

      <div class="stack">
        <div class="mini-metrics">
          <div class="mini-metric">
            <span>Nodes</span>
            <strong>{sampleConceptNodes.length}</strong>
          </div>
          <div class="mini-metric">
            <span>Edges</span>
            <strong>6</strong>
          </div>
        </div>

        <div class="chip-cloud">
          {#each sampleConceptNodes as node}
            <span class="chip">{node.label} · {node.type}</span>
          {/each}
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Run logs</span>
          <h2>File-backed records</h2>
        </div>
        <span class="pill">{sampleLogs.length} rows</span>
      </div>

      <div class="log-list">
        {#each sampleLogs as record}
          <article class="log-item">
            <div class="timeline-meta">
              <span class="event-type">{record.level}</span>
              <span>{record.timestamp}</span>
            </div>
            <p>{record.message}</p>
            <details>
              <summary>Record</summary>
              <pre>{formatJson(record.record)}</pre>
            </details>
          </article>
        {/each}
      </div>
    </article>
  </section>

  <section class="panel export-panel">
    <div class="panel-header">
      <div>
        <span class="kicker">Export</span>
        <h2>Report export preview</h2>
      </div>
      <button class="btn primary compact" type="button" disabled>Export markdown</button>
    </div>

    <div class="export-stack">
      <div class="mini-metrics">
        <div class="mini-metric">
          <span>Format</span>
          <strong>markdown</strong>
        </div>
        <div class="mini-metric">
          <span>Content length</span>
          <strong>548</strong>
        </div>
      </div>

      <p class="notice warn">Snapshot data only. The live standalone demo returns export content from your running API.</p>
      <pre>{sampleExport}</pre>
    </div>
  </section>
</section>

<style>
  .demo-shell {
    width: min(var(--shell-width), calc(100% - (var(--shell-gutter, 1rem) * 2)));
    margin: 0 auto;
    padding: 2rem 0 4rem;
    display: grid;
    gap: 1.5rem;
  }

  .notice-band,
  .hero-copy,
  .hero-note,
  .panel,
  .timeline-panel {
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: var(--shadow);
    backdrop-filter: blur(16px);
    border-radius: 24px;
  }

  .notice-band {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1rem;
    padding: 1.2rem 1.3rem;
    background: linear-gradient(135deg, rgba(22, 50, 79, 0.92), rgba(45, 128, 127, 0.88));
    color: #fff7ef;
  }

  .notice-label {
    display: inline-flex;
    align-items: center;
    height: fit-content;
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.18);
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .notice-band strong {
    display: block;
    margin-bottom: 0.35rem;
  }

  .notice-band p {
    color: rgba(255, 247, 239, 0.86);
  }

  .notice-actions {
    margin-top: 0.55rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: center;
  }

  .notice-actions a {
    color: #fff7ef;
    text-decoration: underline;
  }

  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
    gap: 1.25rem;
    align-items: start;
  }

  .hero-copy {
    padding: 1.8rem;
  }

  .hero-note {
    padding: 1.4rem;
    background: linear-gradient(180deg, rgba(255, 250, 243, 0.92), rgba(244, 235, 223, 0.86));
  }

  .hero-note span,
  .kicker,
  .meta-label {
    display: inline-block;
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.74rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .eyebrow {
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.74rem;
    color: var(--accent);
    margin-bottom: 0.9rem;
  }

  h1 {
    font-size: clamp(2.2rem, 5vw, 3.6rem);
    line-height: 1.02;
    letter-spacing: -0.03em;
    margin-bottom: 0.85rem;
  }

  .lede,
  .hero-note p,
  .summary-copy p,
  .timeline-item p,
  .notice-band p {
    color: var(--text-body);
  }

  .hero-note strong {
    display: block;
    margin: 0.45rem 0 0.55rem;
  }

  .control-grid,
  .inspector-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.5rem;
  }

  .panel,
  .timeline-panel {
    padding: 1.4rem;
  }

  .panel-header,
  .timeline-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
    margin-bottom: 1.25rem;
  }

  .panel-header h2,
  .timeline-header h2 {
    font-size: 1.35rem;
    margin-top: 0.2rem;
  }

  .pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 999px;
    padding: 0.45rem 0.75rem;
    font-size: 0.78rem;
    color: var(--text-body);
    background: rgba(22, 50, 79, 0.06);
    border: 1px solid rgba(22, 50, 79, 0.08);
    white-space: nowrap;
  }

  .stream-connected {
    color: var(--teal);
    border-color: rgba(45, 128, 127, 0.18);
    background: rgba(45, 128, 127, 0.08);
  }

  .run-form,
  .stack,
  .export-stack,
  .approval-list,
  .log-list,
  .summary-stack {
    display: grid;
    gap: 1rem;
  }

  label {
    display: grid;
    gap: 0.42rem;
  }

  label span {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-strong);
  }

  input,
  textarea {
    width: 100%;
    border: 1px solid rgba(22, 50, 79, 0.14);
    border-radius: 16px;
    background: rgba(255, 254, 250, 0.92);
    color: var(--text-strong);
    padding: 0.82rem 0.95rem;
    font: inherit;
    resize: vertical;
  }

  input:disabled,
  textarea:disabled {
    opacity: 0.92;
    cursor: not-allowed;
  }

  .form-row,
  .metrics-grid,
  .mini-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .form-actions,
  .action-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-top: 0.25rem;
  }

  .divider {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0.25rem 0;
  }

  .divider::before {
    content: "";
    position: absolute;
    inset: 50% 0 auto;
    border-top: 1px solid var(--line);
  }

  .divider span {
    position: relative;
    z-index: 1;
    padding: 0 0.8rem;
    background: rgba(255, 251, 244, 0.96);
    color: var(--text-soft);
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .load-run,
  .approval-card,
  .log-item,
  .metric,
  .mini-metric,
  .plain-list li {
    border-radius: 18px;
    border: 1px solid rgba(22, 50, 79, 0.08);
    background: rgba(255, 255, 255, 0.5);
  }

  .load-run,
  .approval-card,
  .log-item {
    padding: 0.95rem;
  }

  .btn {
    border: none;
    border-radius: 999px;
    padding: 0.85rem 1.2rem;
    font: inherit;
    font-weight: 600;
    cursor: not-allowed;
    opacity: 0.78;
  }

  .btn.primary {
    color: white;
    background: linear-gradient(135deg, var(--accent), var(--accent-soft));
    box-shadow: 0 16px 28px rgba(214, 111, 69, 0.22);
  }

  .btn.secondary {
    color: var(--text-strong);
    background: rgba(22, 50, 79, 0.06);
    border: 1px solid rgba(22, 50, 79, 0.1);
  }

  .btn.tertiary {
    color: var(--teal);
    background: rgba(45, 128, 127, 0.08);
    border: 1px solid rgba(45, 128, 127, 0.14);
  }

  .btn.compact {
    padding: 0.65rem 0.95rem;
    font-size: 0.85rem;
  }

  .summary-topline,
  .approval-header,
  .timeline-meta {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
  }

  .run-id {
    display: inline-block;
    margin-top: 0.35rem;
    font-family: "IBM Plex Mono", monospace;
    font-size: 1rem;
  }

  .status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.45rem 0.8rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border: 1px solid transparent;
  }

  .status-awaiting_approval,
  .status-pending {
    background: rgba(214, 111, 69, 0.12);
    color: var(--accent);
    border-color: rgba(214, 111, 69, 0.24);
  }

  .status-not_required {
    background: rgba(45, 128, 127, 0.12);
    color: #216766;
    border-color: rgba(45, 128, 127, 0.28);
  }

  .metric,
  .mini-metric {
    padding: 0.9rem;
  }

  .metric span,
  .mini-metric span {
    display: block;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-soft);
    margin-bottom: 0.35rem;
  }

  .summary-copy,
  .list-block {
    display: grid;
    gap: 0.5rem;
  }

  .summary-foot {
    display: grid;
    gap: 0.45rem;
    padding-top: 0.4rem;
    border-top: 1px solid var(--line);
  }

  .notice {
    color: var(--text-soft);
  }

  .notice.warn {
    color: var(--accent);
  }

  .muted {
    color: var(--text-soft);
    font-style: italic;
  }

  .timeline-list {
    display: grid;
    gap: 0.9rem;
    max-height: min(65vh, 960px);
    overflow-y: auto;
    padding-right: 0.35rem;
  }

  .timeline-item {
    border: 1px solid rgba(22, 50, 79, 0.08);
    border-radius: 20px;
    padding: 1rem 1.05rem;
    background: rgba(255, 255, 255, 0.56);
  }

  .timeline-meta {
    font-size: 0.78rem;
    color: var(--text-soft);
    margin-bottom: 0.55rem;
  }

  .event-type {
    font-family: "IBM Plex Mono", monospace;
    color: var(--teal);
  }

  .plain-list {
    list-style: none;
    padding-left: 0;
    margin: 0;
    display: grid;
    gap: 0.45rem;
  }

  .plain-list li {
    padding: 0.7rem 0.85rem;
    color: var(--text-body);
  }

  .chip-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 0.8rem;
    border-radius: 999px;
    background: rgba(45, 128, 127, 0.08);
    border: 1px solid rgba(45, 128, 127, 0.14);
    color: var(--teal);
    font-size: 0.82rem;
  }

  details {
    margin-top: 0.8rem;
  }

  summary {
    cursor: pointer;
    color: var(--accent);
    font-weight: 600;
  }

  .export-panel {
    padding: 1.4rem;
  }

  @media (max-width: 900px) {
    .hero,
    .control-grid,
    .inspector-grid {
      grid-template-columns: 1fr;
    }

    .metrics-grid,
    .mini-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 640px) {
    .demo-shell {
      width: min(var(--shell-width), calc(100vw - 1rem));
      padding-top: 1.2rem;
    }

    .notice-band {
      grid-template-columns: 1fr;
    }

    .notice-band,
    .hero-copy,
    .hero-note,
    .panel,
    .timeline-panel {
      border-radius: 20px;
    }

    .panel-header,
    .timeline-header,
    .summary-topline,
    .timeline-meta,
    .approval-header,
    .notice-actions {
      flex-direction: column;
      align-items: start;
    }

    .form-row,
    .metrics-grid,
    .mini-metrics {
      grid-template-columns: 1fr;
    }

    .form-actions,
    .action-row {
      flex-direction: column;
    }

    .btn {
      width: 100%;
    }
  }
</style>
