// WealthLoop frontend logic

const NODES = [
  { key: "ingestion", title: "Transaction Ingestion" },
  { key: "categorization", title: "Expense Categorization" },
  { key: "health_assessment", title: "Financial Health" },
  { key: "rag_retrieval", title: "Investment RAG" },
  { key: "recommendation", title: "Recommendation" },
  { key: "compliance_guardrail", title: "Suitability Guardrail" },
  { key: "approval_gate", title: "Human Approval" },
  { key: "execution", title: "Execution" },
];

const PERSONAS = [
  { id: "young_professional", name: "Aditya Rao", blurb: "Aggressive · Wealth growth" },
  { id: "conservative_near_retirement", name: "Sunita Iyer", blurb: "Conservative · Retirement" },
  { id: "freelancer_irregular_income", name: "Kabir Mehta", blurb: "Moderate · Emergency fund" },
];

// Fixed order = the validated adjacency order from the categorical palette check.
const SERIES_META = [
  { key: "ELSS", varName: "--series-elss" },
  { key: "PPF", varName: "--series-ppf" },
  { key: "NPS", varName: "--series-nps" },
  { key: "FD", varName: "--series-fd" },
  { key: "Emergency Fund", varName: "--series-emergency" },
];

const REJECTION_REASONS = ["Too aggressive", "Want more liquidity", "Other"];

// Static, hardcoded plain-language glossary -- 5 fixed terms, no LLM call needed.
const SCHEME_GLOSSARY = {
  ELSS: "A mutual fund that invests in the stock market. Higher growth potential, but value can go up or down. Money is locked for 3 years.",
  PPF: "A government savings account. Very safe, fixed interest, but your money is locked for 15 years.",
  NPS: "A retirement savings scheme backed by the government. Safe, grows steadily, money is accessible only after age 60.",
  FD: "Like a bank fixed deposit — you lock in money for a set time and get guaranteed interest. Very safe, easy to understand.",
  "Emergency Fund": "Money kept aside and easily accessible, for surprise expenses like medical bills or job loss — not invested anywhere.",
};

// Deterministic, template-based risk-appetite framing -- no LLM call.
const RISK_SUMMARY_TEMPLATES = {
  conservative:
    "Based on your profile, we recommend playing it safe — mostly government-backed savings, with a small growth component.",
  aggressive:
    "Based on your profile, we recommend focusing on long-term growth — a larger share in market-linked investments, balanced with some safety.",
  moderate:
    "Based on your profile, we recommend a balanced mix — steady, safe options alongside moderate growth investments.",
};

// Renders "SchemeName (?)" with a lightweight CSS-only tooltip (:hover and
// :focus both trigger it, so it works on hover AND click/tap/keyboard-tab
// without any extra JS event wiring).
function schemeLabelWithGlossary(schemeName) {
  const explanation = SCHEME_GLOSSARY[schemeName];
  const label = escapeHtml(schemeName);
  if (!explanation) return label;
  return `${label}<span class="glossary-trigger" tabindex="0">?<span class="glossary-tooltip" role="tooltip">${escapeHtml(explanation)}</span></span>`;
}

// Perceived-pacing budget per node: quick for simple nodes, longer +
// staggered for RAG citations and the recommendation breakdown.
const TIMING = {
  ingestion: { runningMs: 650, staggerMs: 0 },
  categorization: { runningMs: 850, staggerMs: 90 },
  health_assessment: { runningMs: 650, staggerMs: 0 },
  rag_retrieval: { runningMs: 900, staggerMs: 260 },
  recommendation: { runningMs: 1000, staggerMs: 220 },
  compliance_guardrail: { runningMs: 750, staggerMs: 0 },
  approval_gate: { runningMs: 450, staggerMs: 0 },
  execution: { runningMs: 650, staggerMs: 0 },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let eventSource = null;
let sessionId = null;
let eventQueue = [];
let processingQueue = false;
let attemptCounts = {};
let isFirstEventInRun = true;
let continueResolver = null;
let cards = {}; // nodeKey -> { root, body, statusDot, statusLabel, attemptBadge }
let streamEndedCleanly = false; // suppresses the spurious onerror EventSource fires on any server-side close
let currentRiskAppetite = null; // captured from the ingestion event, used for the plain-language summary line

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatINR(amount) {
  const n = Number(amount) || 0;
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function humanizeFlag(flag) {
  return String(flag)
    .split("_")
    .join(" ")
    .replace(/^./, (c) => c.toUpperCase());
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Pipeline card scaffolding
// ---------------------------------------------------------------------------

function buildPipelineCards() {
  const pipeline = document.getElementById("pipeline");
  pipeline.innerHTML = "";
  cards = {};

  NODES.forEach((node, index) => {
    const root = document.createElement("div");
    root.className = "agent-card";
    root.dataset.status = "pending";
    root.dataset.node = node.key;

    root.innerHTML = `
      <div class="agent-card-header">
        <span class="agent-card-index">${index + 1}</span>
        <span class="agent-card-title">${node.title}</span>
        <span class="attempt-badge" data-role="attempt-badge">Attempt 2</span>
        <span class="status-pill" data-role="status-pill">
          <span class="status-dot"></span>
          <span data-role="status-label">Pending</span>
        </span>
      </div>
      <div class="agent-card-body" data-role="body"></div>
    `;

    pipeline.appendChild(root);

    cards[node.key] = {
      root,
      body: root.querySelector('[data-role="body"]'),
      statusLabel: root.querySelector('[data-role="status-label"]'),
      attemptBadge: root.querySelector('[data-role="attempt-badge"]'),
    };
  });
}

function setCardStatus(nodeKey, status, labelOverride) {
  const card = cards[nodeKey];
  if (!card) return;
  card.root.dataset.status = status;
  const labels = {
    pending: "Pending",
    running: "Running",
    done: "Done",
    approval: "Needs approval",
    flagged: "Flagged",
  };
  card.statusLabel.textContent = labelOverride || labels[status] || status;
}

function openCardBody(nodeKey) {
  cards[nodeKey].body.classList.add("is-open");
}

function showAttemptBadge(nodeKey, attemptNumber) {
  const badge = cards[nodeKey].attemptBadge;
  badge.textContent = `Attempt ${attemptNumber}`;
  badge.classList.add("is-visible");
}

function showLoopBanner(nodeKey, text) {
  const card = cards[nodeKey];
  const banner = document.createElement("div");
  banner.className = "loop-banner";
  banner.innerHTML = `<span>↩</span><span>${escapeHtml(text)}</span>`;
  card.root.insertBefore(banner, card.root.firstChild);
  setTimeout(() => banner.remove(), 1650);
}

// ---------------------------------------------------------------------------
// Renderers -- each returns the inner HTML for a card body given its output
// ---------------------------------------------------------------------------

function renderIngestion(output) {
  const profile = output.user_profile || {};
  const volatility = profile.income_volatility || "stable";
  const pillClass = volatility === "variable" ? "pill-variable" : "pill-stable";
  return `
    <div class="kv-grid reveal-item">
      <div class="kv-item"><div class="kv-label">Name</div><div class="kv-value">${escapeHtml(profile.name)}</div></div>
      <div class="kv-item"><div class="kv-label">Age</div><div class="kv-value">${escapeHtml(profile.age)}</div></div>
      <div class="kv-item"><div class="kv-label">Risk appetite</div><div class="kv-value">${escapeHtml(profile.risk_appetite)}</div></div>
      <div class="kv-item"><div class="kv-label">Financial goal</div><div class="kv-value">${escapeHtml((profile.financial_goal || "").replace(/_/g, " "))}</div></div>
      <div class="kv-item"><div class="kv-label">Avg monthly income</div><div class="kv-value">${formatINR(profile.average_monthly_income)}</div></div>
      <div class="kv-item"><div class="kv-label">Income volatility</div><div class="kv-value"><span class="pill ${pillClass}">${escapeHtml(volatility)}</span></div></div>
    </div>
  `;
}

function renderCategorization(output) {
  const categories = output.expense_categories || {};
  const entries = Object.entries(categories);
  const txCount = (output.transactions || []).length;
  const bars = entries
    .map(([name, stats], i) => `
      <div class="bar-row reveal-item" style="animation-delay:${i * TIMING.categorization.staggerMs}ms">
        <span class="bar-label">${escapeHtml(name)}</span>
        <span class="bar-track"><span class="bar-fill" data-target="${stats.percentage}"></span></span>
        <span class="bar-value">${formatINR(stats.total)}</span>
      </div>
    `)
    .join("");
  return `
    <div class="bar-list">${bars}</div>
    <p class="activated-at reveal-item" style="animation-delay:${entries.length * TIMING.categorization.staggerMs}ms">${txCount} transactions categorized</p>
  `;
}

function renderHealthAssessment(output) {
  return `
    <div class="stat-tiles reveal-item">
      <div class="stat-tile">
        <div class="stat-tile-label">Savings rate</div>
        <div class="stat-tile-value">${output.savings_rate}%</div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Monthly surplus</div>
        <div class="stat-tile-value">${formatINR(output.surplus_amount)}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Emergency fund</div>
        <div class="stat-tile-value">${escapeHtml(output.emergency_fund_status)}</div>
      </div>
    </div>
  `;
}

function schemeColorVar(schemeName) {
  const match = SERIES_META.find((s) => schemeName.toUpperCase().includes(s.key.toUpperCase()));
  return match ? `var(${match.varName})` : "var(--brand-teal-bright)";
}

function renderRagRetrieval(output) {
  const schemes = output.relevant_schemes || [];
  const items = schemes
    .map((chunk, i) => {
      const color = schemeColorVar(chunk.scheme_name || "");
      return `
        <div class="citation-card reveal-item" style="animation-delay:${i * 260}ms">
          <div class="citation-head">
            <span class="scheme-badge" style="background:${color}">${escapeHtml(chunk.scheme_name)}</span>
            <span class="citation-section">${escapeHtml(chunk.section)}</span>
          </div>
          <div class="citation-snippet">${escapeHtml(chunk.chunk_text)}</div>
          <div class="citation-source">Source: ${escapeHtml(chunk.source)}</div>
        </div>
      `;
    })
    .join("");
  return `<div class="citation-list">${items}</div>`;
}

function renderAllocation(allocation) {
  const segmentsHtml = SERIES_META.filter((s) => allocation[s.key])
    .map(
      (s) =>
        `<span class="allocation-segment" data-target="${allocation[s.key].percent}" style="background:var(${s.varName})"></span>`
    )
    .join("");

  const legendHtml = SERIES_META.filter((s) => allocation[s.key])
    .map((s, i) => {
      const entry = allocation[s.key];
      return `
        <div class="legend-row reveal-item" style="animation-delay:${i * 220 + 200}ms">
          <span class="legend-swatch" style="background:var(${s.varName})"></span>
          <span class="legend-name">${schemeLabelWithGlossary(s.key)}</span>
          <span class="legend-percent">${entry.percent}%</span>
          <span class="legend-amount">${formatINR(entry.amount)}</span>
          <span class="legend-reasoning">${escapeHtml(entry.reasoning)}</span>
        </div>
      `;
    })
    .join("");

  return `
    <div class="allocation-bar">${segmentsHtml}</div>
    <div class="allocation-legend">${legendHtml}</div>
  `;
}

function renderRecommendation(output) {
  const summary =
    RISK_SUMMARY_TEMPLATES[currentRiskAppetite] ||
    "Based on your profile, here's a personalized allocation across safe and growth-oriented options.";
  const summaryHtml = `<p class="recommendation-summary reveal-item">${escapeHtml(summary)}</p>`;
  return summaryHtml + renderAllocation(output.recommended_allocation || {});
}

function renderCompliance(output) {
  const flags = output.suitability_flags || [];
  if (!flags.length) {
    return `
      <div class="compliance-result is-pass reveal-item">
        <span class="compliance-icon">✓</span>
        <span>All suitability checks passed — allocation is within policy for this risk profile.</span>
      </div>
    `;
  }
  const flagItems = flags.map((f) => `<li>${escapeHtml(humanizeFlag(f))}</li>`).join("");
  const explanation = output.compliance_explanation
    ? `<p style="margin:8px 0 0;">${escapeHtml(output.compliance_explanation)}</p>`
    : "";
  return `
    <div class="compliance-result is-fail reveal-item">
      <span class="compliance-icon">⚠</span>
      <div>
        <span>Suitability check failed — sending back for revision.</span>
        <ul class="compliance-flag-list">${flagItems}</ul>
        ${explanation}
      </div>
    </div>
  `;
}

function renderExecution(output) {
  const plan = output.final_plan;
  if (!plan) return "";
  const tax = plan.estimated_tax_saved || {};
  return `
    <div class="final-plan-banner reveal-item"><span>✓</span><span>Plan activated</span></div>
    <div class="final-plan-grid reveal-item">
      <div class="stat-tile">
        <div class="stat-tile-label">Monthly SIP</div>
        <div class="stat-tile-value">${formatINR(plan.monthly_sip)}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Annual deployment</div>
        <div class="stat-tile-value">${formatINR(plan.annual_deployment)}</div>
      </div>
    </div>
    <div class="tax-breakdown reveal-item">
      <div class="tax-breakdown-row"><span>80C eligible (${schemeLabelWithGlossary("ELSS")} + ${schemeLabelWithGlossary("PPF")})</span><span>${formatINR(tax.annual_80c_eligible)}</span></div>
      <div class="tax-breakdown-row"><span>80CCD(1B) eligible (${schemeLabelWithGlossary("NPS")})</span><span>${formatINR(tax.annual_80ccd1b_eligible)}</span></div>
      <div class="tax-breakdown-row is-total"><span>Est. annual tax saved (@${tax.assumed_marginal_tax_rate_pct}%)</span><span>${formatINR(tax.estimated_annual_tax_saved)}</span></div>
    </div>
    <div class="activated-at reveal-item">Activated at ${escapeHtml(plan.activated_at)}</div>
  `;
}

const RENDERERS = {
  ingestion: renderIngestion,
  categorization: renderCategorization,
  health_assessment: renderHealthAssessment,
  rag_retrieval: renderRagRetrieval,
  recommendation: renderRecommendation,
  compliance_guardrail: renderCompliance,
  execution: renderExecution,
};

// Animate bar/segment widths on the next frame so the CSS transition fires.
function animateFillsIn(container) {
  requestAnimationFrame(() => {
    container.querySelectorAll("[data-target]").forEach((el) => {
      el.style.width = `${el.dataset.target}%`;
    });
  });
}

// ---------------------------------------------------------------------------
// Event processing
// ---------------------------------------------------------------------------

function enqueueEvent(event) {
  eventQueue.push(event);
  if (!processingQueue) {
    processingQueue = true;
    processQueue();
  }
}

// Step-through mode: frontend-only pacing control. It never touches the
// backend/graph -- SSE events keep arriving and buffering in eventQueue
// exactly as normal; this just delays *dequeuing* the next one until the
// user clicks Continue. Read live (not cached) so toggling mid-run works.
function describeUpcomingEvent(event) {
  if (event.node === "done") return "Completion";
  if (event.status === "awaiting_approval") return "Human Approval (awaiting your decision)";
  const meta = NODES.find((n) => n.key === event.node);
  return meta ? meta.title : event.node;
}

function waitForContinue(nextEvent) {
  return new Promise((resolve) => {
    continueResolver = resolve;
    document.getElementById("step-through-hint").textContent = `Paused -- up next: ${describeUpcomingEvent(nextEvent)}`;
    document.getElementById("step-through-bar").hidden = false;
  });
}

function resolveContinue() {
  document.getElementById("step-through-bar").hidden = true;
  if (continueResolver) {
    const resolve = continueResolver;
    continueResolver = null;
    resolve();
  }
}

async function processQueue() {
  while (eventQueue.length) {
    const stepThrough = document.getElementById("step-through-toggle").checked;
    if (stepThrough && !isFirstEventInRun) {
      await waitForContinue(eventQueue[0]);
    }
    const event = eventQueue.shift();
    isFirstEventInRun = false;
    await handleEvent(event);
  }
  processingQueue = false;
}

async function handleEvent(event) {
  if (event.node === "done") {
    finalize();
    return;
  }

  if (event.status === "awaiting_approval") {
    await activateApprovalCard(event.payload);
    return;
  }

  if (event.node === "approval_gate") {
    handleApprovalResolved(event.output);
    return;
  }

  await activateNodeCard(event.node, event.output);
}

async function activateNodeCard(nodeKey, output) {
  const timing = TIMING[nodeKey] || { runningMs: 700, staggerMs: 0 };

  if (nodeKey === "ingestion") {
    currentRiskAppetite = (output.user_profile || {}).risk_appetite || null;
  }

  attemptCounts[nodeKey] = (attemptCounts[nodeKey] || 0) + 1;
  const attempt = attemptCounts[nodeKey];

  if (nodeKey === "recommendation" && attempt > 1) {
    showLoopBanner(nodeKey, `Revising based on feedback — attempt ${attempt}`);
    showAttemptBadge(nodeKey, attempt);
  }

  setCardStatus(nodeKey, "running");

  const itemCount =
    nodeKey === "rag_retrieval"
      ? (output.relevant_schemes || []).length
      : nodeKey === "recommendation"
      ? Object.keys(output.recommended_allocation || {}).length
      : nodeKey === "categorization"
      ? Object.keys(output.expense_categories || {}).length
      : 0;
  const totalDelay = timing.runningMs + itemCount * timing.staggerMs;

  await sleep(timing.runningMs);

  const card = cards[nodeKey];
  const renderer = RENDERERS[nodeKey];
  if (renderer) {
    card.body.innerHTML = renderer(output);
    openCardBody(nodeKey);
    animateFillsIn(card.body);
  }

  if (nodeKey === "compliance_guardrail") {
    const failed = (output.suitability_flags || []).length > 0;
    setCardStatus(nodeKey, failed ? "flagged" : "done", failed ? "Flagged" : "Passed");
  } else {
    setCardStatus(nodeKey, "done");
  }

  // Let staggered children finish their own reveal animation before the
  // queue moves on to the next node.
  await sleep(Math.max(0, totalDelay - timing.runningMs));
}

let approveHandlersBound = false;

async function activateApprovalCard(payload) {
  const nodeKey = "approval_gate";
  setCardStatus(nodeKey, "running", "Awaiting approval");
  await sleep(TIMING.approval_gate.runningMs);

  const card = cards[nodeKey];
  const summary = payload.summary || {};
  const allocation = payload.recommended_allocation || {};

  card.body.innerHTML = `
    <div class="approval-recap reveal-item">
      <div class="stat-tiles" style="margin-bottom:14px;">
        <div class="stat-tile">
          <div class="stat-tile-label">Savings rate</div>
          <div class="stat-tile-value">${summary.savings_rate_pct}%</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile-label">Monthly surplus</div>
          <div class="stat-tile-value">${formatINR(summary.surplus_amount)}</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile-label">Emergency fund</div>
          <div class="stat-tile-value">${escapeHtml(summary.emergency_fund_status)}</div>
        </div>
      </div>
      ${renderAllocation(allocation)}
    </div>
    <div class="approval-actions" data-role="approval-actions">
      <button class="btn-approve" data-role="approve-btn" type="button">Approve</button>
      <button class="btn-reject" data-role="reject-btn" type="button">Reject</button>
    </div>
    <div class="reject-panel" data-role="reject-panel">
      <div class="reject-panel-label">Select a reason (required)</div>
      <div class="chip-row" data-role="chip-row">
        ${REJECTION_REASONS.map((r) => `<button class="reason-chip" type="button" data-reason="${escapeHtml(r)}">${escapeHtml(r)}</button>`).join("")}
      </div>
      <button class="btn-reject" data-role="confirm-reject-btn" type="button" disabled>Confirm Rejection</button>
    </div>
    <div class="approval-note" data-role="approval-note"></div>
  `;
  openCardBody(nodeKey);
  animateFillsIn(card.body);
  setCardStatus(nodeKey, "approval");

  wireApprovalActions(card);
}

function wireApprovalActions(card) {
  const approveBtn = card.body.querySelector('[data-role="approve-btn"]');
  const rejectBtn = card.body.querySelector('[data-role="reject-btn"]');
  const rejectPanel = card.body.querySelector('[data-role="reject-panel"]');
  const chipRow = card.body.querySelector('[data-role="chip-row"]');
  const confirmRejectBtn = card.body.querySelector('[data-role="confirm-reject-btn"]');
  const note = card.body.querySelector('[data-role="approval-note"]');
  let selectedReason = null;

  function disableAll() {
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
    confirmRejectBtn.disabled = true;
    chipRow.querySelectorAll(".reason-chip").forEach((c) => (c.disabled = true));
  }

  approveBtn.addEventListener("click", async () => {
    disableAll();
    note.textContent = "Sending approval…";
    note.className = "approval-note";
    await submitApproval({ approval_status: "approved" });
    note.textContent = "Approved — proceeding to execution.";
    note.className = "approval-note is-approved";
  });

  rejectBtn.addEventListener("click", () => {
    rejectPanel.classList.add("is-open");
    rejectBtn.disabled = true;
  });

  chipRow.querySelectorAll(".reason-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chipRow.querySelectorAll(".reason-chip").forEach((c) => c.classList.remove("is-selected"));
      chip.classList.add("is-selected");
      selectedReason = chip.dataset.reason;
      confirmRejectBtn.disabled = false;
    });
  });

  confirmRejectBtn.addEventListener("click", async () => {
    if (!selectedReason) return;
    disableAll();
    note.textContent = "Sending rejection…";
    note.className = "approval-note";
    await submitApproval({ approval_status: "rejected", rejection_reason: selectedReason });
    note.textContent = `Rejected (${selectedReason}) — sending back for revision.`;
    note.className = "approval-note is-rejected";
  });
}

async function submitApproval(body) {
  try {
    const res = await fetch(`/api/approve/${sessionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      console.error("approve request failed", res.status, await res.text());
    }
  } catch (err) {
    console.error("approve request error", err);
  }
}

function handleApprovalResolved(output) {
  setCardStatus("approval_gate", "done", output.approval_status === "approved" ? "Approved" : "Rejected");
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

function setModalStatus(text, complete) {
  const el = document.getElementById("modal-status-line");
  el.textContent = text;
  el.classList.toggle("is-complete", !!complete);
}

function finalize() {
  setModalStatus("✓ Analysis complete — plan activated", true);
  streamEndedCleanly = true;
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  document.getElementById("analyze-btn").disabled = false;
}

async function startAnalysis() {
  const personaSelect = document.getElementById("persona-select");
  const personaId = personaSelect.value;
  const persona = PERSONAS.find((p) => p.id === personaId);

  document.getElementById("analyze-btn").disabled = true;
  attemptCounts = {};
  eventQueue = [];
  processingQueue = false;
  streamEndedCleanly = false;
  isFirstEventInRun = true;
  currentRiskAppetite = null;
  resolveContinue();

  buildPipelineCards();
  document.getElementById("modal-persona-name").textContent = persona ? persona.name : personaId;
  setModalStatus("Starting analysis…", false);
  document.getElementById("overlay").hidden = false;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: personaId }),
    });
    if (!res.ok) throw new Error(`analyze failed: ${res.status}`);
    const data = await res.json();
    sessionId = data.session_id;

    setModalStatus("Running agent pipeline…", false);

    if (eventSource) eventSource.close();
    eventSource = new EventSource(`/api/stream/${sessionId}`);
    eventSource.onmessage = (e) => {
      const payload = JSON.parse(e.data);
      // Set this on receipt, not once the queued animation gets around to
      // processing it -- the server closes the socket right after sending
      // "done", which can race ahead of our (deliberately paced) rendering.
      if (payload.node === "done") streamEndedCleanly = true;
      enqueueEvent(payload);
    };
    eventSource.onerror = (err) => {
      // Native EventSource fires "error" whenever the connection ends, even
      // on a graceful server-side close after the "done" event -- so only
      // treat it as a real problem if we didn't already finish cleanly.
      if (streamEndedCleanly) return;
      console.error("SSE error", err);
      if (eventSource && eventSource.readyState === EventSource.CLOSED) {
        setModalStatus("Connection lost.", false);
        document.getElementById("analyze-btn").disabled = false;
      }
    };
  } catch (err) {
    console.error(err);
    setModalStatus("Failed to start analysis. See console for details.", false);
    document.getElementById("analyze-btn").disabled = false;
  }
}

function closeModal() {
  document.getElementById("overlay").hidden = true;
  streamEndedCleanly = true;
  resolveContinue();
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  document.getElementById("analyze-btn").disabled = false;
}

function init() {
  const select = document.getElementById("persona-select");
  select.innerHTML = PERSONAS.map((p) => `<option value="${p.id}">${escapeHtml(p.name)} — ${escapeHtml(p.blurb)}</option>`).join("");

  document.getElementById("analyze-btn").addEventListener("click", startAnalysis);
  document.getElementById("close-modal-btn").addEventListener("click", closeModal);
  document.getElementById("continue-btn").addEventListener("click", resolveContinue);
}

document.addEventListener("DOMContentLoaded", init);
