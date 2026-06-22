<script>
  import { onDestroy, onMount } from "svelte";

  const DEFAULT_API_BASE = "/v1";
  const API_BASE_STORAGE_KEY = "deep-research-demo:api-base";
  const POLL_INTERVAL_MS = 2500;
  const TERMINAL_STATUSES = new Set(["completed", "failed", "awaiting_approval", "interrupted"]);
  const APPROVAL_ACTIONS = ["approved", "rejected"];
  const EVENT_TYPES = [
    "run.started",
    "run.resumed",
    "run.failed",
    "scope.proposed",
    "approval.requested",
    "approval.decided",
    "perspective.created",
    "question.created",
    "query.executed",
    "source.accepted",
    "evidence.extracted",
    "claim.created",
    "contradiction.detected",
    "coverage.updated",
    "outline.proposed",
    "section.generated",
    "verification.failed",
    "verification.passed",
    "node.started",
    "node.completed",
    "node.failed",
    "route.selected",
    "budget.checked",
    "policy.applied",
    "policy.denied",
    "stop.evaluated",
    "intervention.submitted",
    "checkpoint.created",
    "checkpoint.restored",
    "report.generated",
    "run.completed"
  ];
  const DEFAULT_FORM = {
    title: "ADK tool governance deep research demo",
    primaryQuestion:
      "How should a Google ADK-based research assistant govern tool usage safely in an enterprise environment?",
    decisionToSupport: "Choose runtime guardrails for production rollout",
    tenantId: "demo",
    userId: "architect-01",
    mode: "review_first"
  };

  let form = { ...DEFAULT_FORM };
  let apiBase = DEFAULT_API_BASE;
  let runId = "";
  let runSummary = null;
  let progress = null;
  let events = [];
  let approvalsData = null;
  let graphData = null;
  let conceptMapData = null;
  let logsData = null;
  let exportData = null;
  let createError = "";
  let runError = "";
  let inspectorError = "";
  let approvalError = "";
  let exportError = "";
  let submitPending = false;
  let initialLoadPending = false;
  let inspectorPending = false;
  let exportPending = false;
  let approvalActionPending = "";
  let pollNotice = "";
  let streamState = "idle";
  let streamNotice = "Start a run to attach the live event stream.";
  let approvalRationale = "";
  let activeRunToken = 0;
  let supplementarySnapshotKey = "";

  let pollTimer = null;
  let eventSource = null;

  function normalizedApiBase() {
    const trimmed = apiBase.trim();
    return trimmed ? trimmed.replace(/\/+$/, "") : DEFAULT_API_BASE;
  }

  function apiUrl(path) {
    const base = normalizedApiBase();
    const relativePath = path.replace(/^\/+/, "");

    if (base.startsWith("http://") || base.startsWith("https://")) {
      return new URL(relativePath, `${base}/`);
    }

    const normalizedBasePath = base.replace(/^\/+/, "");
    return new URL(`${normalizedBasePath}/${relativePath}`, window.location.origin);
  }

  async function readResponse(response) {
    const text = await response.text();

    if (!text) {
      return {};
    }

    try {
      return JSON.parse(text);
    } catch {
      return {
        rawText: text,
        contentType: response.headers.get("content-type") ?? ""
      };
    }
  }

  function nonJsonErrorMessage(response, payload, url) {
    const rawText = typeof payload?.rawText === "string" ? payload.rawText.trim() : "";
    const contentType = typeof payload?.contentType === "string" ? payload.contentType : "";
    const base = normalizedApiBase();

    if (response.status === 404 && rawText.startsWith("<!doctype html")) {
      return `Received an HTML 404 from ${url}. This frontend is not proxying API requests. Set API Base URL to your backend origin, for example http://127.0.0.1:8000/v1.`;
    }

    if (rawText) {
      const preview = rawText.replace(/\s+/g, " ").slice(0, 180);
      return `Request failed with status ${response.status}. Response was ${contentType || "non-JSON"}: ${preview}`;
    }

    return `Request failed with status ${response.status}. Response was ${contentType || "non-JSON"}.`;
  }

  async function request(path, options = {}) {
    const url = apiUrl(path);
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers ?? {})
      }
    });
    const payload = await readResponse(response);

    if (!response.ok) {
      const detail =
        typeof payload?.detail === "string"
          ? payload.detail
          : typeof payload?.message === "string"
            ? payload.message
            : nonJsonErrorMessage(response, payload, url);
      throw new Error(detail);
    }

    return payload;
  }

  function persistApiBase() {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(API_BASE_STORAGE_KEY, normalizedApiBase());
    }
  }

  async function createRun(payload) {
    return request("/research-runs", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async function fetchRunSummary(targetRunId) {
    return request(`/research-runs/${targetRunId}`);
  }

  async function fetchRunProgress(targetRunId) {
    return request(`/research-runs/${targetRunId}/progress`);
  }

  async function fetchApprovals(targetRunId) {
    return request(`/research-runs/${targetRunId}/approvals`);
  }

  async function fetchGraph(targetRunId) {
    return request(`/research-runs/${targetRunId}/graph`);
  }

  async function fetchConceptMap(targetRunId) {
    return request(`/research-runs/${targetRunId}/concept-map`);
  }

  async function fetchLogs(targetRunId, limit = 50) {
    return request(`/research-runs/${targetRunId}/logs?limit=${limit}`);
  }

  async function submitApproval(targetRunId, approvalId, payload) {
    return request(`/research-runs/${targetRunId}/approvals/${approvalId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async function exportRun(targetRunId, format = "markdown") {
    return request(`/research-runs/${targetRunId}/exports?format=${format}`, {
      method: "POST"
    });
  }

  function resetRunState() {
    runSummary = null;
    progress = null;
    events = [];
    approvalsData = null;
    graphData = null;
    conceptMapData = null;
    logsData = null;
    exportData = null;
    runError = "";
    inspectorError = "";
    approvalError = "";
    exportError = "";
    approvalActionPending = "";
    approvalRationale = "";
    pollNotice = "";
    streamState = "idle";
    streamNotice = "Start a run to attach the live event stream.";
    supplementarySnapshotKey = "";
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function stopEventStream() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function stopWatchingRun() {
    stopPolling();
    stopEventStream();
  }

  function appendEvent(eventRecord) {
    const duplicate = events.some((event) => {
      return (
        event.timestamp === eventRecord.timestamp &&
        event.event_type === eventRecord.event_type &&
        JSON.stringify(event.payload) === JSON.stringify(eventRecord.payload)
      );
    });

    if (duplicate) {
      return;
    }

    events = [eventRecord, ...events].slice(0, 200);
  }

  function formatTimestamp(value) {
    if (!value) {
      return "Unknown time";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      month: "short",
      day: "numeric"
    }).format(date);
  }

  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }

  function summarizeLogRecord(record) {
    if (typeof record?.message === "string" && record.message.trim()) {
      return record.message;
    }

    return "No log message";
  }

  function summarizeClaim(claim) {
    return (
      claim?.statement ??
      claim?.text ??
      claim?.claim ??
      claim?.summary ??
      claim?.claim_id ??
      "Unnamed claim"
    );
  }

  function summarizeSource(source) {
    return source?.title ?? source?.url ?? source?.source_id ?? "Unnamed source";
  }

  function sortedApprovals() {
    return Object.entries(approvalsData?.approvals ?? {}).sort(([left], [right]) => left.localeCompare(right));
  }

  async function hydrateSupplementaryData(targetRunId, token) {
    inspectorPending = true;
    inspectorError = "";

    const results = await Promise.allSettled([
      fetchApprovals(targetRunId),
      fetchGraph(targetRunId),
      fetchConceptMap(targetRunId),
      fetchLogs(targetRunId)
    ]);

    if (token !== activeRunToken) {
      return;
    }

    const [approvalsResult, graphResult, conceptMapResult, logsResult] = results;
    const failures = [];

    if (approvalsResult.status === "fulfilled") {
      approvalsData = approvalsResult.value;
    } else {
      failures.push("approvals");
    }

    if (graphResult.status === "fulfilled") {
      graphData = graphResult.value;
    } else {
      failures.push("graph");
    }

    if (conceptMapResult.status === "fulfilled") {
      conceptMapData = conceptMapResult.value;
    } else {
      failures.push("concept map");
    }

    if (logsResult.status === "fulfilled") {
      logsData = logsResult.value;
    } else {
      failures.push("logs");
    }

    inspectorError =
      failures.length > 0
        ? `Some Phase 2 panels could not refresh: ${failures.join(", ")}.`
        : "";
    inspectorPending = false;
  }

  function maybeHydrateSupplementary(targetRunId, status, token) {
    const nextKey = `${targetRunId}:${TERMINAL_STATUSES.has(status) ? status : "live"}`;

    if (supplementarySnapshotKey === nextKey && graphData && conceptMapData && logsData) {
      return;
    }

    supplementarySnapshotKey = nextKey;
    hydrateSupplementaryData(targetRunId, token);
  }

  function summarizeEvent(eventRecord) {
    const payload = eventRecord?.payload ?? {};

    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }

    if (typeof payload.node_name === "string" && payload.node_name.trim()) {
      return payload.node_name;
    }

    if (typeof payload.phase === "string" && payload.phase.trim()) {
      return `Phase: ${payload.phase}`;
    }

    if (typeof payload.status === "string" && payload.status.trim()) {
      return `Status: ${payload.status}`;
    }

    const usefulKeys = Object.keys(payload).filter((key) => key !== "run_id");
    if (usefulKeys.length === 0) {
      return "No additional event payload.";
    }

    return usefulKeys.slice(0, 3).join(" · ");
  }

  async function refreshRunState(targetRunId, token) {
    try {
      const [nextSummary, nextProgress] = await Promise.all([
        fetchRunSummary(targetRunId),
        fetchRunProgress(targetRunId)
      ]);

      if (token !== activeRunToken) {
        return;
      }

      runSummary = nextSummary;
      progress = nextProgress;
      runError = "";
      pollNotice = `Polling every ${Math.round(POLL_INTERVAL_MS / 1000)}s`;
      maybeHydrateSupplementary(targetRunId, nextSummary.status, token);

      if (TERMINAL_STATUSES.has(runSummary.status)) {
        stopPolling();
        if (runSummary.status !== "failed") {
          streamNotice =
            runSummary.status === "awaiting_approval"
              ? "Run paused for approval. Phase 2 adds a basic approval action panel below."
              : "Run reached a terminal state.";
        }
      }
    } catch (error) {
      if (token !== activeRunToken) {
        return;
      }

      runError = error instanceof Error ? error.message : "Unable to refresh run state.";
      pollNotice = "Polling failed. Retrying while the run remains active.";
    } finally {
      if (token === activeRunToken) {
        initialLoadPending = false;
      }
    }
  }

  function connectEventStream(targetRunId, token) {
    stopEventStream();
    streamState = "connecting";
    streamNotice = "Connecting to live event stream…";

    const source = new EventSource(apiUrl(`/research-runs/${targetRunId}/events`));
    eventSource = source;

    source.onopen = () => {
      if (token !== activeRunToken) {
        source.close();
        return;
      }

      streamState = "connected";
      streamNotice = "Live stream connected.";
    };

    const handleEvent = (message) => {
      if (token !== activeRunToken) {
        return;
      }

      try {
        appendEvent(JSON.parse(message.data));
      } catch {
        streamNotice = "Received an event that could not be parsed.";
      }
    };

    for (const eventType of EVENT_TYPES) {
      source.addEventListener(eventType, handleEvent);
    }

    source.onerror = () => {
      if (token !== activeRunToken) {
        return;
      }

      streamState = "disconnected";
      streamNotice = TERMINAL_STATUSES.has(runSummary?.status)
        ? "Live stream closed after the run stopped changing."
        : "Live stream disconnected. The browser may retry automatically.";
    };
  }

  function startWatchingRun(targetRunId) {
    stopWatchingRun();
    const token = activeRunToken + 1;
    activeRunToken = token;
    initialLoadPending = true;
    refreshRunState(targetRunId, token);
    connectEventStream(targetRunId, token);

    pollTimer = setInterval(() => {
      refreshRunState(targetRunId, token);
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    persistApiBase();
    submitPending = true;
    createError = "";
    runError = "";
    resetRunState();
    stopWatchingRun();

    try {
      const createdRun = await createRun({
        objective: {
          title: form.title,
          primary_question: form.primaryQuestion,
          decision_to_support: form.decisionToSupport
        },
        tenant_id: form.tenantId,
        user_id: form.userId,
        mode: form.mode
      });

      runId = createdRun.run_id;
      runSummary = createdRun;
      startWatchingRun(runId);
    } catch (error) {
      createError = error instanceof Error ? error.message : "Unable to create research run.";
    } finally {
      submitPending = false;
    }
  }

  async function handleRefreshPanels() {
    if (!runId) {
      return;
    }

    supplementarySnapshotKey = "";
    await hydrateSupplementaryData(runId, activeRunToken);
  }

  async function handleApprovalAction(approvalId, decision) {
    if (!runId) {
      return;
    }

    approvalActionPending = `${approvalId}:${decision}`;
    approvalError = "";

    try {
      await submitApproval(runId, approvalId, {
        decision,
        rationale: approvalRationale,
        approver_id: form.userId
      });
      supplementarySnapshotKey = "";
      await hydrateSupplementaryData(runId, activeRunToken);
      startWatchingRun(runId);
    } catch (error) {
      approvalError = error instanceof Error ? error.message : "Unable to submit approval.";
    } finally {
      approvalActionPending = "";
    }
  }

  async function handleExport() {
    if (!runId) {
      return;
    }

    exportPending = true;
    exportError = "";

    try {
      exportData = await exportRun(runId);
    } catch (error) {
      exportError = error instanceof Error ? error.message : "Unable to export report.";
    } finally {
      exportPending = false;
    }
  }

  onMount(() => {
    const saved = window.localStorage.getItem(API_BASE_STORAGE_KEY);
    if (saved) {
      apiBase = saved;
    }
  });

  onDestroy(() => {
    stopWatchingRun();
  });
</script>

<svelte:head>
  <title>Deep Research Assistant Demo</title>
  <meta
    name="description"
    content="Phase 2 demo surface for creating a Deep Research Assistant run, streaming events, handling approvals, and inspecting runtime artifacts."
  />
</svelte:head>

<section class="demo-shell">
  <header class="hero">
    <div class="hero-copy">
      <div class="eyebrow">Phase 2 demo surface</div>
      <h1>Start a research run, watch it stream, and inspect the live runtime state.</h1>
      <p class="lede">
        This page keeps the original streaming demo flow and adds the next operator-facing surfaces:
        basic approvals, graph and concept-map inspection, file-backed logs, and report export.
      </p>
    </div>

    <div class="hero-note">
      <span>API target</span>
      <strong><code>{normalizedApiBase()}</code></strong>
      <p>Use a full backend origin here when this standalone frontend is deployed without a proxy.</p>
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

      <form class="run-form" on:submit={handleSubmit}>
        <label>
          <span>API Base URL</span>
          <input
            bind:value={apiBase}
            name="api-base"
            placeholder="http://127.0.0.1:8000/v1"
            on:blur={persistApiBase}
          />
        </label>

        <label>
          <span>Title</span>
          <input bind:value={form.title} name="title" required />
        </label>

        <label>
          <span>Primary question</span>
          <textarea bind:value={form.primaryQuestion} name="primary-question" rows="4" required></textarea>
        </label>

        <label>
          <span>Decision to support</span>
          <textarea bind:value={form.decisionToSupport} name="decision-to-support" rows="3"></textarea>
        </label>

        <div class="form-row">
          <label>
            <span>Tenant ID</span>
            <input bind:value={form.tenantId} name="tenant-id" required />
          </label>

          <label>
            <span>User ID</span>
            <input bind:value={form.userId} name="user-id" required />
          </label>
        </div>

        <label>
          <span>Mode</span>
          <input bind:value={form.mode} name="mode" required />
        </label>

        <div class="form-actions">
          <button class="btn primary" type="submit" disabled={submitPending}>
            {submitPending ? "Starting run…" : "Start research run"}
          </button>
          <button class="btn secondary" type="button" on:click={() => (form = { ...DEFAULT_FORM })}>
            Reset defaults
          </button>
        </div>

        {#if createError}
          <p class="notice error">{createError}</p>
        {/if}
      </form>
    </article>

    <article class="panel summary-panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Current run</span>
          <h2>Live status summary</h2>
        </div>
        <span class:stream-connected={streamState === "connected"} class="pill">
          {streamState === "connected"
            ? "SSE connected"
            : streamState === "connecting"
              ? "SSE connecting"
              : streamState === "disconnected"
                ? "SSE disconnected"
                : "SSE idle"}
        </span>
      </div>

      {#if !runId}
        <div class="empty-state">
          <p>No run has been created in this session yet.</p>
          <small>The summary card will populate after the first successful POST.</small>
        </div>
      {:else if initialLoadPending && !runSummary}
        <div class="empty-state">
          <p>Loading run summary…</p>
          <small>Fetching `GET /v1/research-runs/{runId}` and `/progress`.</small>
        </div>
      {:else}
        <div class="summary-stack">
          <div class="summary-topline">
            <div>
              <span class="meta-label">Run ID</span>
              <strong class="run-id">{runId}</strong>
            </div>
            <span class={`status status-${runSummary?.status ?? "unknown"}`}>
              {runSummary?.status ?? "unknown"}
            </span>
          </div>

          <div class="metrics-grid">
            <div class="metric">
              <span>Phase</span>
              <strong>{progress?.phase ?? "Loading…"}</strong>
            </div>
            <div class="metric">
              <span>Questions</span>
              <strong>{runSummary?.questions_count ?? 0}</strong>
            </div>
            <div class="metric">
              <span>Claims</span>
              <strong>{runSummary?.claims_count ?? 0}</strong>
            </div>
            <div class="metric">
              <span>Sources</span>
              <strong>{runSummary?.sources_count ?? 0}</strong>
            </div>
          </div>

          <div class="summary-copy">
            <div>
              <span class="meta-label">Title</span>
              <p>{runSummary?.objective?.title ?? "Untitled run"}</p>
            </div>

            <div>
              <span class="meta-label">Primary question</span>
              <p>{runSummary?.objective?.primary_question ?? "No primary question returned."}</p>
            </div>

            <div>
              <span class="meta-label">Report preview</span>
              <p class:muted={!runSummary?.report_preview}>
                {runSummary?.report_preview ?? "No report preview yet."}
              </p>
            </div>
          </div>

          <div class="summary-foot">
            <p class="notice">{pollNotice || "Polling will begin after the run is created."}</p>
            <p class={`notice ${streamState === "disconnected" ? "warn" : ""}`}>{streamNotice}</p>
            {#if runError}
              <p class="notice error">{runError}</p>
            {/if}
          </div>
        </div>
      {/if}
    </article>
  </section>

  <section class="timeline-panel">
    <div class="panel-header timeline-header">
      <div>
        <span class="kicker">Timeline</span>
        <h2>Live workflow events</h2>
      </div>
      <span class="pill">{events.length} event{events.length === 1 ? "" : "s"}</span>
    </div>

    {#if !runId}
      <div class="empty-state wide">
        <p>The event timeline will begin once a run is created.</p>
        <small>The page uses browser-native <code>EventSource</code> against <code>/events</code>.</small>
      </div>
    {:else if events.length === 0}
      <div class="empty-state wide">
        <p>No events have arrived yet.</p>
        <small>Early runs may remain quiet until the workflow emits its first state transition.</small>
      </div>
    {:else}
      <div class="timeline-list">
        {#each events as eventRecord}
          <article class="timeline-item">
            <div class="timeline-meta">
              <span class="event-type">{eventRecord.event_type}</span>
              <span>{formatTimestamp(eventRecord.timestamp)}</span>
            </div>
            <p>{summarizeEvent(eventRecord)}</p>
            <details>
              <summary>Payload</summary>
              <pre>{formatJson(eventRecord.payload)}</pre>
            </details>
          </article>
        {/each}
      </div>
    {/if}
  </section>

  <section class="inspector-grid" aria-label="Phase 2 run inspection panels">
    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Approvals</span>
          <h2>Gate decisions</h2>
        </div>
        <button class="btn tertiary" type="button" on:click={handleRefreshPanels} disabled={!runId || inspectorPending}>
          {inspectorPending ? "Refreshing…" : "Refresh panels"}
        </button>
      </div>

      {#if !runId}
        <div class="empty-state">
          <p>Approval state appears after a run exists.</p>
          <small>Pending gates can be approved or rejected here in Phase 2.</small>
        </div>
      {:else if sortedApprovals().length === 0}
        <div class="empty-state">
          <p>No approval records yet.</p>
          <small>Auto-approved or unfinished runs may not have gate decisions to show.</small>
        </div>
      {:else}
        <div class="stack">
          <label>
            <span>Shared rationale</span>
            <textarea
              bind:value={approvalRationale}
              name="approval-rationale"
              rows="3"
              placeholder="Optional rationale for the next approval action"
            ></textarea>
          </label>

          <div class="approval-list">
            {#each sortedApprovals() as [approvalId, approval]}
              <article class="approval-card">
                <div class="approval-header">
                  <div>
                    <span class="meta-label">Gate {approvalId}</span>
                    <p class="approval-title">{approval?.gate ?? approvalId}</p>
                  </div>
                  <span class={`status status-${approval?.status ?? "unknown"}`}>
                    {approval?.status ?? "unknown"}
                  </span>
                </div>

                <p class:muted={!approval?.rationale}>
                  {approval?.rationale ?? "No rationale recorded."}
                </p>

                {#if approval?.status === "pending" || runSummary?.status === "awaiting_approval"}
                  <div class="action-row">
                    {#each APPROVAL_ACTIONS as decision}
                      <button
                        class="btn secondary compact"
                        type="button"
                        disabled={approvalActionPending === `${approvalId}:${decision}`}
                        on:click={() => handleApprovalAction(approvalId, decision)}
                      >
                        {approvalActionPending === `${approvalId}:${decision}`
                          ? `${decision}…`
                          : decision}
                      </button>
                    {/each}
                  </div>
                {/if}
              </article>
            {/each}
          </div>

          {#if approvalError}
            <p class="notice error">{approvalError}</p>
          {/if}
        </div>
      {/if}
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Research graph</span>
          <h2>Claims and sources</h2>
        </div>
        <span class="pill">
          {(graphData?.claims?.length ?? 0) + (graphData?.sources?.length ?? 0)} records
        </span>
      </div>

      {#if !runId}
        <div class="empty-state">
          <p>The graph view appears after a run starts.</p>
          <small>This panel reads <code>/graph</code> and stays summary-level for now.</small>
        </div>
      {:else if !graphData}
        <div class="empty-state">
          <p>Graph data has not loaded yet.</p>
          <small>Use “Refresh panels” if the run summary is already available.</small>
        </div>
      {:else}
        <div class="stack">
          <div class="mini-metrics">
            <div class="mini-metric">
              <span>Claims</span>
              <strong>{graphData.claims?.length ?? 0}</strong>
            </div>
            <div class="mini-metric">
              <span>Sources</span>
              <strong>{graphData.sources?.length ?? 0}</strong>
            </div>
          </div>

          <div class="list-block">
            <span class="meta-label">Recent claims</span>
            {#if (graphData.claims?.length ?? 0) === 0}
              <p class="muted">No claims recorded yet.</p>
            {:else}
              <ul class="plain-list">
                {#each graphData.claims.slice(0, 4) as claim}
                  <li>{summarizeClaim(claim)}</li>
                {/each}
              </ul>
            {/if}
          </div>

          <div class="list-block">
            <span class="meta-label">Recent sources</span>
            {#if (graphData.sources?.length ?? 0) === 0}
              <p class="muted">No sources recorded yet.</p>
            {:else}
              <ul class="plain-list">
                {#each graphData.sources.slice(0, 4) as source}
                  <li>{summarizeSource(source)}</li>
                {/each}
              </ul>
            {/if}
          </div>
        </div>
      {/if}
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Concept map</span>
          <h2>Topic projection</h2>
        </div>
        <span class="pill">{conceptMapData?.version ?? 0} version</span>
      </div>

      {#if !runId}
        <div class="empty-state">
          <p>The concept map is generated from the underlying run graph.</p>
          <small>It becomes useful once questions, claims, and evidence exist.</small>
        </div>
      {:else if !conceptMapData}
        <div class="empty-state">
          <p>Concept map data has not loaded yet.</p>
          <small>Use “Refresh panels” to fetch the current projection.</small>
        </div>
      {:else}
        <div class="stack">
          <div class="mini-metrics">
            <div class="mini-metric">
              <span>Nodes</span>
              <strong>{conceptMapData.topic_nodes?.length ?? 0}</strong>
            </div>
            <div class="mini-metric">
              <span>Edges</span>
              <strong>{conceptMapData.edges?.length ?? 0}</strong>
            </div>
          </div>

          {#if (conceptMapData.topic_nodes?.length ?? 0) === 0}
            <p class="muted">No topic nodes projected yet.</p>
          {:else}
            <div class="chip-cloud">
              {#each conceptMapData.topic_nodes.slice(0, 8) as node}
                <span class="chip">{node.label} · {node.type}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </article>

    <article class="panel">
      <div class="panel-header">
        <div>
          <span class="kicker">Run logs</span>
          <h2>File-backed records</h2>
        </div>
        <span class="pill">{logsData?.count ?? 0} rows</span>
      </div>

      {#if !runId}
        <div class="empty-state">
          <p>Logs are scoped to a persisted run id.</p>
          <small>This panel reads the backend’s filtered JSON log records.</small>
        </div>
      {:else if !logsData}
        <div class="empty-state">
          <p>Logs have not loaded yet.</p>
          <small>Use “Refresh panels” to pull the latest log slice.</small>
        </div>
      {:else if (logsData.records?.length ?? 0) === 0}
        <div class="empty-state">
          <p>No run logs were returned.</p>
          <small>The backend may not have persisted any records yet for this run.</small>
        </div>
      {:else}
        <div class="log-list">
          {#each logsData.records.slice(0, 8) as record}
            <article class="log-item">
              <div class="timeline-meta">
                <span class="event-type">{record.level ?? "INFO"}</span>
                <span>{formatTimestamp(record.timestamp)}</span>
              </div>
              <p>{summarizeLogRecord(record)}</p>
              <details>
                <summary>Record</summary>
                <pre>{formatJson(record)}</pre>
              </details>
            </article>
          {/each}
        </div>
      {/if}
    </article>
  </section>

  <section class="panel export-panel">
    <div class="panel-header">
      <div>
        <span class="kicker">Export</span>
        <h2>Report export preview</h2>
      </div>
      <button class="btn primary compact" type="button" on:click={handleExport} disabled={!runId || exportPending}>
        {exportPending ? "Exporting…" : "Export markdown"}
      </button>
    </div>

    {#if !runId}
      <div class="empty-state wide">
        <p>Export preview is available after a run exists.</p>
        <small>The backend currently returns the report body inline rather than a file artifact.</small>
      </div>
    {:else if !exportData}
      <div class="empty-state wide">
        <p>No export requested yet.</p>
        <small>Use the button above to call <code>POST /exports?format=markdown</code>.</small>
      </div>
    {:else}
      <div class="export-stack">
        <div class="mini-metrics">
          <div class="mini-metric">
            <span>Format</span>
            <strong>{exportData.format}</strong>
          </div>
          <div class="mini-metric">
            <span>Content length</span>
            <strong>{exportData.content_length}</strong>
          </div>
        </div>

        {#if exportData.note}
          <p class="notice warn">{exportData.note}</p>
        {/if}

        <pre>{exportData.content}</pre>
      </div>
    {/if}

    {#if exportError}
      <p class="notice error">{exportError}</p>
    {/if}
    {#if inspectorError}
      <p class="notice warn">{inspectorError}</p>
    {/if}
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

  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
    gap: 1.25rem;
    align-items: start;
  }

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
  .empty-state p {
    color: var(--text-body);
  }

  .hero-note strong {
    display: block;
    margin: 0.45rem 0 0.55rem;
  }

  .control-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 1.5rem;
  }

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

  .run-form {
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
    transition:
      border-color 140ms ease,
      box-shadow 140ms ease,
      transform 140ms ease;
  }

  input:focus,
  textarea:focus {
    outline: none;
    border-color: rgba(214, 111, 69, 0.5);
    box-shadow: 0 0 0 4px rgba(214, 111, 69, 0.12);
  }

  .form-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .form-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-top: 0.25rem;
  }

  .btn {
    border: none;
    border-radius: 999px;
    padding: 0.85rem 1.2rem;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    transition:
      transform 140ms ease,
      box-shadow 140ms ease,
      opacity 140ms ease;
  }

  .btn:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  .btn:disabled {
    cursor: wait;
    opacity: 0.72;
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

  .empty-state {
    min-height: 100%;
    display: grid;
    align-content: center;
    justify-items: start;
    gap: 0.35rem;
    padding: 1rem 0.2rem 0.4rem;
  }

  .empty-state.wide {
    min-height: 220px;
    justify-items: center;
    text-align: center;
  }

  .empty-state small,
  .notice {
    color: var(--text-soft);
  }

  .summary-stack {
    display: grid;
    gap: 1rem;
  }

  .summary-topline {
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

  .status-queued {
    background: rgba(239, 180, 91, 0.12);
    color: #9d6a07;
    border-color: rgba(239, 180, 91, 0.28);
  }

  .status-running {
    background: rgba(45, 128, 127, 0.1);
    color: var(--teal);
    border-color: rgba(45, 128, 127, 0.24);
  }

  .status-completed {
    background: rgba(45, 128, 127, 0.14);
    color: #216766;
    border-color: rgba(45, 128, 127, 0.3);
  }

  .status-awaiting_approval,
  .status-interrupted {
    background: rgba(214, 111, 69, 0.12);
    color: var(--accent);
    border-color: rgba(214, 111, 69, 0.24);
  }

  .status-failed {
    background: rgba(124, 38, 51, 0.1);
    color: #7c2633;
    border-color: rgba(124, 38, 51, 0.24);
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .metric {
    padding: 0.9rem;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.5);
    border: 1px solid rgba(22, 50, 79, 0.07);
  }

  .metric span {
    display: block;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-soft);
    margin-bottom: 0.35rem;
  }

  .metric strong {
    font-size: 1.05rem;
  }

  .summary-copy {
    display: grid;
    gap: 0.85rem;
  }

  .summary-copy p {
    margin-top: 0.28rem;
  }

  .muted {
    color: var(--text-soft);
    font-style: italic;
  }

  .summary-foot {
    display: grid;
    gap: 0.45rem;
    padding-top: 0.4rem;
    border-top: 1px solid var(--line);
  }

  .stack,
  .export-stack {
    display: grid;
    gap: 1rem;
  }

  .approval-list,
  .log-list {
    display: grid;
    gap: 0.8rem;
  }

  .approval-card,
  .log-item {
    border: 1px solid rgba(22, 50, 79, 0.08);
    border-radius: 18px;
    padding: 0.95rem;
    background: rgba(255, 255, 255, 0.52);
  }

  .approval-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    margin-bottom: 0.65rem;
  }

  .approval-title {
    margin-top: 0.25rem;
    color: var(--text-strong);
    font-weight: 600;
  }

  .action-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 0.8rem;
  }

  .status-approved,
  .status-not_required {
    background: rgba(45, 128, 127, 0.12);
    color: #216766;
    border-color: rgba(45, 128, 127, 0.28);
  }

  .status-rejected {
    background: rgba(124, 38, 51, 0.1);
    color: #7c2633;
    border-color: rgba(124, 38, 51, 0.24);
  }

  .status-pending {
    background: rgba(239, 180, 91, 0.14);
    color: #9d6a07;
    border-color: rgba(239, 180, 91, 0.26);
  }

  .mini-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .mini-metric {
    padding: 0.85rem;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.52);
    border: 1px solid rgba(22, 50, 79, 0.07);
  }

  .mini-metric span {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-soft);
    margin-bottom: 0.3rem;
  }

  .list-block {
    display: grid;
    gap: 0.5rem;
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
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.46);
    border: 1px solid rgba(22, 50, 79, 0.06);
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

  .export-panel {
    padding: 1.4rem;
  }

  .notice.warn {
    color: var(--accent);
  }

  .notice.error {
    color: #8b2d3a;
  }

  .timeline-list {
    display: grid;
    gap: 0.9rem;
  }

  .timeline-item {
    border: 1px solid rgba(22, 50, 79, 0.08);
    border-radius: 20px;
    padding: 1rem 1.05rem;
    background: rgba(255, 255, 255, 0.56);
  }

  .timeline-meta {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    font-size: 0.78rem;
    color: var(--text-soft);
    margin-bottom: 0.55rem;
  }

  .event-type {
    font-family: "IBM Plex Mono", monospace;
    color: var(--teal);
  }

  details {
    margin-top: 0.8rem;
  }

  summary {
    cursor: pointer;
    color: var(--accent);
    font-weight: 600;
  }

  pre {
    margin-bottom: 0;
    white-space: pre-wrap;
    word-break: break-word;
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
    .approval-header {
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
