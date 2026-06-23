<script>
  import { onDestroy, onMount } from "svelte";

  const DEFAULT_API_BASE = "http://localhost:8080/v1";
  const API_BASE_STORAGE_KEY = "deep-research-demo:api-base";
  const POLL_INTERVAL_MS = 2500;
  const SUPPLEMENTARY_REFRESH_MS = 5000;
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
  const MODE_OPTIONS = [
    { value: "autonomous", label: "Autonomous" },
    { value: "collaborative", label: "Collaborative" },
    { value: "review_first", label: "Review first" },
    { value: "continuous_watch", label: "Continuous watch" }
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
  const EMPTY_ERROR_STATE = null;

  let form = { ...DEFAULT_FORM };
  let apiBase = DEFAULT_API_BASE;
  let existingRunId = "";
  let runId = "";
  let runSummary = null;
  let progress = null;
  let events = [];
  let approvalsData = null;
  let graphData = null;
  let conceptMapData = null;
  let logsData = null;
  let exportData = null;
  let createError = EMPTY_ERROR_STATE;
  let runError = EMPTY_ERROR_STATE;
  let inspectorError = EMPTY_ERROR_STATE;
  let approvalError = EMPTY_ERROR_STATE;
  let exportError = EMPTY_ERROR_STATE;
  let submitPending = false;
  let loadPending = false;
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
  let lastSupplementaryRefreshAt = 0;

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
      return `Received an HTML 404 from ${url}. This frontend is not proxying API requests. Set API Base URL to your backend origin, for example http://localhost:8080/v1.`;
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

  function normalizeError(error, fallbackDetail) {
    if (error instanceof Error && error.message.trim()) {
      return error.message.trim();
    }

    return fallbackDetail;
  }

  function describeError(error, context) {
    const detail = normalizeError(error, context.defaultDetail);

    if (detail.includes("DEEP_RESEARCH_EXA_API_KEY")) {
      return {
        title: "Backend provider configuration is missing",
        detail,
        hint: "Set DEEP_RESEARCH_EXA_API_KEY on the API server, then retry the run."
      };
    }

    if (detail.includes("Received an HTML 404")) {
      return {
        title: "API Base URL points at the wrong origin",
        detail,
        hint: "Use the backend origin, usually http://localhost:8080/v1, not the static frontend host."
      };
    }

    if (detail === "Failed to fetch" || detail.includes("NetworkError")) {
      return {
        title: "The API server could not be reached",
        detail,
        hint: "Check that the backend is running and that this browser origin is allowed by CORS."
      };
    }

    if (detail.includes("status 503")) {
      return {
        title: "The backend is temporarily unavailable",
        detail,
        hint: "Check the API server logs and runtime configuration, then try again."
      };
    }

    if (detail.includes("status 404")) {
      return {
        title: context.notFoundTitle,
        detail,
        hint: context.notFoundHint
      };
    }

    return {
      title: context.title,
      detail,
      hint: context.hint
    };
  }

  function persistApiBase() {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(API_BASE_STORAGE_KEY, normalizedApiBase());
    }
  }

  function syncUrlState(nextRunId = runId) {
    if (typeof window === "undefined") {
      return;
    }

    const url = new URL(window.location.href);
    const normalizedBase = normalizedApiBase();

    if (nextRunId) {
      url.searchParams.set("run_id", nextRunId);
    } else {
      url.searchParams.delete("run_id");
    }

    if (normalizedBase && normalizedBase !== DEFAULT_API_BASE) {
      url.searchParams.set("api_base", normalizedBase);
    } else {
      url.searchParams.delete("api_base");
    }

    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
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
    runError = EMPTY_ERROR_STATE;
    inspectorError = EMPTY_ERROR_STATE;
    approvalError = EMPTY_ERROR_STATE;
    exportError = EMPTY_ERROR_STATE;
    approvalActionPending = "";
    approvalRationale = "";
    pollNotice = "";
    streamState = "idle";
    streamNotice = "Start a run to attach the live event stream.";
    supplementarySnapshotKey = "";
    lastSupplementaryRefreshAt = 0;
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

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function renderInlineMarkdown(value) {
    let html = escapeHtml(value);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    );
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return html;
  }

  function renderMarkdown(markdown) {
    if (!markdown) {
      return "";
    }

    const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let paragraph = [];
    let listItems = [];
    let inCodeBlock = false;
    let codeLines = [];

    function flushParagraph() {
      if (paragraph.length === 0) {
        return;
      }

      html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
      paragraph = [];
    }

    function flushList() {
      if (listItems.length === 0) {
        return;
      }

      html.push(`<ol>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ol>`);
      listItems = [];
    }

    function flushCodeBlock() {
      if (!inCodeBlock) {
        return;
      }

      html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      inCodeBlock = false;
      codeLines = [];
    }

    for (const line of lines) {
      if (line.startsWith("```")) {
        flushParagraph();
        flushList();
        if (inCodeBlock) {
          flushCodeBlock();
        } else {
          inCodeBlock = true;
        }
        continue;
      }

      if (inCodeBlock) {
        codeLines.push(line);
        continue;
      }

      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        flushParagraph();
        flushList();
        const level = heading[1].length;
        html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
        continue;
      }

      const orderedItem = line.match(/^\d+\.\s+(.*)$/);
      if (orderedItem) {
        flushParagraph();
        listItems.push(orderedItem[1]);
        continue;
      }

      const bulletItem = line.match(/^[-*]\s+(.*)$/);
      if (bulletItem) {
        flushParagraph();
        listItems.push(bulletItem[1]);
        continue;
      }

      if (!line.trim()) {
        flushParagraph();
        flushList();
        continue;
      }

      flushList();
      paragraph.push(line.trim());
    }

    flushParagraph();
    flushList();
    flushCodeBlock();
    return html.join("");
  }

  function sortedApprovals() {
    return Object.entries(approvalsData?.approvals ?? {}).sort(([left], [right]) => left.localeCompare(right));
  }

  function activeApprovalEntry() {
    const pendingGate = runSummary?.awaiting_approval_gate;
    const approvals = approvalsData?.approvals ?? {};

    if (pendingGate && approvals[pendingGate]) {
      return [pendingGate, approvals[pendingGate]];
    }

    const pendingEntry = Object.entries(approvals).find(([, approval]) => approval?.status === "pending");
    if (pendingEntry) {
      return pendingEntry;
    }

    if (pendingGate) {
      return [
        pendingGate,
        {
          gate: pendingGate,
          status: "pending",
          rationale: "",
          display_data: {}
        }
      ];
    }

    return null;
  }

  function gateLabel(gateId) {
    const labels = {
      A: "Scope approval",
      B: "Research plan approval",
      C: "Outline approval",
      D: "Publication approval"
    };

    return labels[gateId] ?? `Gate ${gateId}`;
  }

  function summarizeApproval(approvalId, approval) {
    const displayData = approval?.display_data ?? {};

    if (approvalId === "A") {
      const objective = displayData.objective ?? {};
      const scope = displayData.scope ?? {};
      const perspectives = Array.isArray(displayData.proposed_perspectives)
        ? displayData.proposed_perspectives.length
        : 0;
      const budget = displayData.budget ?? {};

      return {
        title: objective.title ?? "Approve proposed research scope",
        items: [
          `Risk level: ${displayData.risk_level ?? scope.risk_level ?? "unknown"}`,
          `Primary question: ${objective.primary_question ?? "not provided"}`,
          `Proposed perspectives: ${perspectives}`,
          `Budgeted searches: ${budget.searches ?? "n/a"}`
        ]
      };
    }

    if (approvalId === "B") {
      return {
        title: "Approve the research plan before execution",
        items: [
          `Questions: ${Array.isArray(displayData.questions) ? displayData.questions.length : 0}`,
          `Perspectives: ${Array.isArray(displayData.perspectives) ? displayData.perspectives.length : 0}`,
          `Limitations: ${Array.isArray(displayData.limitations) ? displayData.limitations.length : 0}`
        ]
      };
    }

    if (approvalId === "C") {
      const sourceMix = displayData.source_mix ?? {};
      return {
        title: "Approve the draft outline and evidence posture",
        items: [
          `Principal claims: ${Array.isArray(displayData.principal_claims) ? displayData.principal_claims.length : 0}`,
          `Sources: ${sourceMix.sources ?? 0}`,
          `Evidence fragments: ${sourceMix.evidence ?? 0}`
        ]
      };
    }

    if (approvalId === "D") {
      const riskIndicators = displayData.risk_indicators ?? {};
      return {
        title: "Approve publication or external distribution",
        items: [
          `Final claims: ${Array.isArray(displayData.final_claims) ? displayData.final_claims.length : 0}`,
          `Risk level: ${riskIndicators.risk_level ?? "unknown"}`,
          `Blocking findings: ${riskIndicators.blocking_findings ?? 0}`
        ]
      };
    }

    return {
      title: "Approve this workflow gate",
      items: []
    };
  }

  async function hydrateSupplementaryData(targetRunId, token) {
    if (inspectorPending) {
      return;
    }

    inspectorPending = true;
    inspectorError = EMPTY_ERROR_STATE;

    try {
      const results = await Promise.allSettled([
        fetchApprovals(targetRunId),
        fetchGraph(targetRunId),
        fetchConceptMap(targetRunId),
        fetchLogs(targetRunId)
      ]);

      if (token !== activeRunToken) {
        return;
      }

      lastSupplementaryRefreshAt = Date.now();

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
          ? {
              title: "Some inspector panels did not refresh",
              detail: `The following panels failed to load: ${failures.join(", ")}.`,
              hint: "The run can still be inspected. Retry after the API becomes reachable."
            }
          : EMPTY_ERROR_STATE;
    } finally {
      inspectorPending = false;
    }
  }

  function maybeHydrateSupplementary(targetRunId, status, token) {
    const isTerminal = TERMINAL_STATUSES.has(status);
    const nextKey = `${targetRunId}:${isTerminal ? status : "live"}`;

    if (isTerminal) {
      if (
        supplementarySnapshotKey === nextKey &&
        approvalsData &&
        graphData &&
        conceptMapData &&
        logsData
      ) {
        return;
      }

      supplementarySnapshotKey = nextKey;
      hydrateSupplementaryData(targetRunId, token);
      return;
    }

    const hasHydratedLiveData = approvalsData && graphData && conceptMapData && logsData;
    const refreshIsDue = Date.now() - lastSupplementaryRefreshAt >= SUPPLEMENTARY_REFRESH_MS;

    supplementarySnapshotKey = nextKey;
    if (!hasHydratedLiveData || refreshIsDue) {
      hydrateSupplementaryData(targetRunId, token);
    }
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
      runError = EMPTY_ERROR_STATE;
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

      runError = describeError(error, {
        title: "The run summary could not be refreshed",
        defaultDetail: "Unable to refresh run state.",
        notFoundTitle: "The requested run was not found",
        notFoundHint: "Check the run id and API base URL, then try loading the run again.",
        hint: "Retry once the API server is reachable."
      });
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
    createError = EMPTY_ERROR_STATE;
    runError = EMPTY_ERROR_STATE;
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
      existingRunId = createdRun.run_id;
      runSummary = createdRun;
      syncUrlState(createdRun.run_id);
      startWatchingRun(runId);
    } catch (error) {
      createError = describeError(error, {
        title: "The research run could not be created",
        defaultDetail: "Unable to create research run.",
        notFoundTitle: "The API route was not found",
        notFoundHint: "Check the API base URL. It should usually end with /v1.",
        hint: "Review the request and backend logs, then retry."
      });
    } finally {
      submitPending = false;
    }
  }

  async function handleLoadExistingRun(event) {
    event.preventDefault();
    const targetRunId = existingRunId.trim();

    if (!targetRunId) {
      createError = {
        title: "A run id is required",
        detail: "Enter a run id to load an existing research run.",
        hint: "Paste a previously created run id and try again."
      };
      return;
    }

    persistApiBase();
    loadPending = true;
    createError = EMPTY_ERROR_STATE;
    runError = EMPTY_ERROR_STATE;
    resetRunState();
    stopWatchingRun();

    try {
      runId = targetRunId;
      existingRunId = targetRunId;
      syncUrlState(targetRunId);
      startWatchingRun(targetRunId);
    } catch (error) {
      createError = describeError(error, {
        title: "The requested run could not be loaded",
        defaultDetail: "Unable to load research run.",
        notFoundTitle: "The run could not be found",
        notFoundHint: "Confirm the run id exists on this backend and that the API base URL is correct.",
        hint: "Retry after confirming the backend is reachable."
      });
    } finally {
      loadPending = false;
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
    approvalError = EMPTY_ERROR_STATE;

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
      approvalError = describeError(error, {
        title: "The approval decision could not be submitted",
        defaultDetail: "Unable to submit approval.",
        notFoundTitle: "The approval target was not found",
        notFoundHint: "Refresh the run state to confirm the gate still exists before retrying.",
        hint: "Retry after the run summary has refreshed."
      });
    } finally {
      approvalActionPending = "";
    }
  }

  async function handleExport() {
    if (!runId) {
      return;
    }

    exportPending = true;
    exportError = EMPTY_ERROR_STATE;

    try {
      exportData = await exportRun(runId);
    } catch (error) {
      exportError = describeError(error, {
        title: "The report export could not be generated",
        defaultDetail: "Unable to export report.",
        notFoundTitle: "The export target was not found",
        notFoundHint: "Reload the run and retry the export once the backend confirms it exists.",
        hint: "Retry after the run reaches a stable state."
      });
    } finally {
      exportPending = false;
    }
  }

  onMount(() => {
    const url = new URL(window.location.href);
    const saved = window.localStorage.getItem(API_BASE_STORAGE_KEY);
    const apiBaseParam = url.searchParams.get("api_base");
    const runIdParam = url.searchParams.get("run_id");

    if (apiBaseParam) {
      apiBase = apiBaseParam;
    } else if (saved) {
      apiBase = saved;
    }

    if (runIdParam) {
      existingRunId = runIdParam;
      runId = runIdParam;
      syncUrlState(runIdParam);
      startWatchingRun(runIdParam);
    } else {
      syncUrlState("");
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
            placeholder="http://localhost:8080/v1"
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
          <select bind:value={form.mode} name="mode" required>
            {#each MODE_OPTIONS as option}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
        </label>

        <div class="form-actions">
          <button class="btn primary" type="submit" disabled={submitPending}>
            {submitPending ? "Starting run…" : "Start research run"}
          </button>
          <button class="btn secondary" type="button" on:click={() => (form = { ...DEFAULT_FORM })}>
            Reset defaults
          </button>
        </div>

        <div class="divider">
          <span>or</span>
        </div>

        <div class="load-run">
          <label>
            <span>Existing Run ID</span>
            <input bind:value={existingRunId} name="existing-run-id" placeholder="071521de" />
          </label>

          <button class="btn tertiary" type="button" on:click={handleLoadExistingRun} disabled={loadPending}>
            {loadPending ? "Loading run…" : "Load existing run"}
          </button>
        </div>

        {#if createError}
          <div class="error-card" role="alert">
            <strong>{createError.title}</strong>
            <p>{createError.detail}</p>
            {#if createError.hint}
              <small>{createError.hint}</small>
            {/if}
          </div>
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
            {#if runSummary?.status === "awaiting_approval" && activeApprovalEntry()}
              {@const [approvalId, approval] = activeApprovalEntry()}
              {@const summary = summarizeApproval(approvalId, approval)}
              <div class="approval-banner" role="alert">
                <div class="approval-banner-copy">
                  <span class="meta-label">Approval required</span>
                  <p>{gateLabel(approvalId)}. {summary.title}</p>
                </div>

                {#if summary.items.length > 0}
                  <ul class="approval-summary-list">
                    {#each summary.items as item}
                      <li>{item}</li>
                    {/each}
                  </ul>
                {/if}

                <div class="action-row">
                  {#each APPROVAL_ACTIONS as decision}
                    <button
                      class="btn secondary compact"
                      type="button"
                      disabled={approvalActionPending === `${approvalId}:${decision}`}
                      on:click={() => handleApprovalAction(approvalId, decision)}
                    >
                      {approvalActionPending === `${approvalId}:${decision}` ? `${decision}…` : decision}
                    </button>
                  {/each}
                </div>
              </div>
            {/if}

            <p class="notice">{pollNotice || "Polling will begin after the run is created."}</p>
            <p class={`notice ${streamState === "disconnected" ? "warn" : ""}`}>{streamNotice}</p>
            {#if runError}
              <div class="error-card" role="alert">
                <strong>{runError.title}</strong>
                <p>{runError.detail}</p>
                {#if runError.hint}
                  <small>{runError.hint}</small>
                {/if}
              </div>
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

          <div class="approval-list scroll-pane">
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

                {#if true}
                  {@const summary = summarizeApproval(approvalId, approval)}
                  <div class="approval-context">
                    <p class="approval-context-title">{summary.title}</p>
                    {#if summary.items.length > 0}
                      <ul class="approval-summary-list">
                        {#each summary.items as item}
                          <li>{item}</li>
                        {/each}
                      </ul>
                    {/if}
                    <details>
                      <summary>Review payload</summary>
                      <pre>{formatJson(approval?.display_data ?? {})}</pre>
                    </details>
                  </div>
                {/if}

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
            <div class="error-card" role="alert">
              <strong>{approvalError.title}</strong>
              <p>{approvalError.detail}</p>
              {#if approvalError.hint}
                <small>{approvalError.hint}</small>
              {/if}
            </div>
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
              <ul class="plain-list scroll-pane">
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
            <div class="chip-cloud scroll-pane">
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
        <div class="log-list scroll-pane">
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

        <div class="markdown-report">{@html renderMarkdown(exportData.content)}</div>
      </div>
    {/if}

    {#if exportError}
      <div class="error-card" role="alert">
        <strong>{exportError.title}</strong>
        <p>{exportError.detail}</p>
        {#if exportError.hint}
          <small>{exportError.hint}</small>
        {/if}
      </div>
    {/if}
    {#if inspectorError}
      <div class="error-card warn" role="status">
        <strong>{inspectorError.title}</strong>
        <p>{inspectorError.detail}</p>
        {#if inspectorError.hint}
          <small>{inspectorError.hint}</small>
        {/if}
      </div>
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

  .load-run {
    display: grid;
    gap: 0.85rem;
    padding: 1rem;
    border-radius: 18px;
    border: 1px solid rgba(22, 50, 79, 0.08);
    background: rgba(255, 255, 255, 0.4);
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

  .error-card {
    display: grid;
    gap: 0.35rem;
    padding: 0.95rem 1rem;
    border-radius: 18px;
    border: 1px solid rgba(124, 38, 51, 0.18);
    background: rgba(124, 38, 51, 0.06);
    color: #7c2633;
  }

  .error-card strong {
    font-size: 0.92rem;
  }

  .error-card p,
  .error-card small {
    color: inherit;
  }

  .error-card.warn {
    border-color: rgba(214, 111, 69, 0.18);
    background: rgba(214, 111, 69, 0.08);
    color: #9f582f;
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

  .approval-banner {
    display: grid;
    gap: 0.8rem;
    padding: 0.95rem 1rem;
    border-radius: 18px;
    border: 1px solid rgba(214, 111, 69, 0.22);
    background: rgba(214, 111, 69, 0.08);
  }

  .approval-banner-copy {
    display: grid;
    gap: 0.3rem;
  }

  .approval-banner-copy p {
    margin: 0;
  }

  .approval-summary-list {
    margin: 0;
    padding-left: 1.1rem;
    color: var(--text-soft);
    display: grid;
    gap: 0.2rem;
  }

  .approval-context {
    display: grid;
    gap: 0.6rem;
  }

  .approval-context-title {
    margin: 0;
    font-weight: 600;
  }

  .stack,
  .export-stack {
    display: grid;
    gap: 1rem;
  }

  .markdown-report {
    display: grid;
    gap: 0.9rem;
    padding: 1.1rem;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.52);
    border: 1px solid rgba(22, 50, 79, 0.07);
  }

  .markdown-report :global(h1),
  .markdown-report :global(h2),
  .markdown-report :global(h3),
  .markdown-report :global(h4),
  .markdown-report :global(h5),
  .markdown-report :global(h6) {
    margin: 0;
    line-height: 1.15;
  }

  .markdown-report :global(p),
  .markdown-report :global(ol),
  .markdown-report :global(ul),
  .markdown-report :global(pre) {
    margin: 0;
  }

  .markdown-report :global(ol),
  .markdown-report :global(ul) {
    padding-left: 1.4rem;
  }

  .markdown-report :global(li) {
    color: var(--text-body);
    margin: 0.3rem 0;
  }

  .approval-list,
  .log-list {
    display: grid;
    gap: 0.8rem;
  }

  .scroll-pane {
    max-height: 24rem;
    overflow-y: auto;
    padding-right: 0.35rem;
    scrollbar-gutter: stable;
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
