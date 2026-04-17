const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const templateSelect = document.getElementById("templateSelect");
const sessionInfoEl = document.getElementById("sessionInfo");
const insightBoxEl = document.getElementById("insightBox");
const newSessionBtn = document.getElementById("newSessionBtn");
const sendBtn = document.getElementById("sendBtn");
const agentPanelEl = document.getElementById("agentPanel");

let sessionId = null;
let loadingMessageNode = null;
let loadingTickerId = null;

const pipelineTemplate = [
  { name: "Orchestrator", detail: "Routing workflow" },
  { name: "Planner", detail: "Building task graph" },
  { name: "SubResearch t1", detail: "Background + scope" },
  { name: "SubResearch t2", detail: "Paper collection" },
  { name: "SubResearch t3", detail: "Method analysis" },
  { name: "SubResearch t4", detail: "Synthesis input prep" },
  { name: "Critic", detail: "Confidence scoring" },
  { name: "Combiner", detail: "Section merging" },
  { name: "Citation Verifier", detail: "Citation integrity check" },
  { name: "Composer", detail: "LaTeX generation" },
  { name: "Exporter", detail: "Writing output artifacts" },
];

function appendMessage(role, text, options = {}) {
  const node = document.createElement("article");
  node.className = `message ${role}`;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "You" : "Research Agent";
  node.appendChild(meta);

  const content = document.createElement("div");
  content.textContent = text;
  node.appendChild(content);

  if (options.generating) {
    node.classList.add("generating");
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.innerHTML = "<span></span><span></span><span></span>";
    node.appendChild(typing);
  }

  if (options.links) {
    const links = document.createElement("div");
    links.className = "links";
    Object.entries(options.links)
      .filter(([, href]) => Boolean(href))
      .forEach(([label, href]) => {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = label;
      links.appendChild(link);
      });
    node.appendChild(links);
  }

  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return node;
}

function normalizeStatus(value) {
  const normalized = String(value || "idle").toLowerCase();
  if (["complete", "completed", "done"].includes(normalized)) return "complete";
  if (["running", "in_progress", "executing"].includes(normalized)) return "running";
  if (["waiting", "awaiting_user_clarification"].includes(normalized)) return "waiting";
  if (["blocked", "error", "failed"].includes(normalized)) return normalized;
  if (["pending"].includes(normalized)) return "pending";
  return "idle";
}

function renderAgentActivity(entries) {
  const safeEntries = Array.isArray(entries) ? entries : [];
  if (!safeEntries.length) {
    agentPanelEl.innerHTML = `
      <div class="agent-row idle">
        <span class="agent-name">No active run</span>
        <span class="agent-pill idle">idle</span>
      </div>`;
    return;
  }

  agentPanelEl.innerHTML = "";
  safeEntries.forEach((entry) => {
    const status = normalizeStatus(entry.status);
    const row = document.createElement("div");
    row.className = "agent-row";

    const name = document.createElement("span");
    name.className = "agent-name";
    name.textContent = entry.name || "Agent";

    const pill = document.createElement("span");
    pill.className = `agent-pill ${status}`;
    pill.textContent = status;

    row.appendChild(name);
    row.appendChild(pill);

    if (entry.detail) {
      const detail = document.createElement("div");
      detail.className = "detail";
      detail.textContent = entry.detail;
      row.appendChild(detail);
    }

    agentPanelEl.appendChild(row);
  });
}

function startLoadingActivity() {
  stopLoadingActivity();
  let idx = 0;

  loadingTickerId = window.setInterval(() => {
    const entries = pipelineTemplate.map((step, stepIdx) => {
      let status = "pending";
      if (stepIdx < idx) status = "complete";
      if (stepIdx === idx) status = "running";
      return { ...step, status };
    });
    renderAgentActivity(entries);
    idx = (idx + 1) % pipelineTemplate.length;
  }, 550);
}

function stopLoadingActivity() {
  if (loadingTickerId) {
    window.clearInterval(loadingTickerId);
    loadingTickerId = null;
  }
}

function startGeneratingUI() {
  sendBtn.disabled = true;
  messageInput.disabled = true;
  loadingMessageNode = appendMessage("assistant", "Generating research output...", {
    generating: true,
  });
  startLoadingActivity();
}

function stopGeneratingUI() {
  sendBtn.disabled = false;
  messageInput.disabled = false;
  stopLoadingActivity();
  if (loadingMessageNode && loadingMessageNode.parentElement) {
    loadingMessageNode.parentElement.removeChild(loadingMessageNode);
  }
  loadingMessageNode = null;
}

async function ensureSession() {
  if (sessionId) {
    return sessionId;
  }

  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template: templateSelect.value }),
  });

  if (!response.ok) {
    throw new Error("Failed to create session.");
  }

  const payload = await response.json();
  sessionId = payload.session_id;
  sessionInfoEl.textContent = `Session: ${sessionId}`;
  return sessionId;
}

function renderInsights(payload) {
  if (payload.kind !== "result") {
    insightBoxEl.textContent = "Clarification phase active.";
    renderAgentActivity(payload.agent_activity || []);
    return;
  }

  const confidence = Object.entries(payload.section_confidence || {})
    .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
    .join("\n");

  const notes = (payload.critic_notes || []).map((x) => `- ${x}`).join("\n") || "- none";
  const warnings = (payload.warnings || []).slice(0, 6).map((x) => `- ${x}`).join("\n") || "- none";

  insightBoxEl.textContent = [
    `Run: ${payload.run_id || "n/a"}`,
    "",
    "Confidence:",
    confidence || "n/a",
    "",
    "Critic:",
    notes,
    "",
    "Warnings:",
    warnings,
  ].join("\n");

  renderAgentActivity(payload.agent_activity || []);
}

async function sendMessage(text) {
  const sid = await ensureSession();

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sid,
      message: text,
      template: templateSelect.value,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Request failed");
  }

  return response.json();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  messageInput.value = "";
  startGeneratingUI();

  try {
    const payload = await sendMessage(text);

    if (payload.kind === "clarification") {
      const questionText = [payload.assistant_message, "", ...(payload.questions || []).map((q, i) => `${i + 1}. ${q}`)].join("\n");
      appendMessage("assistant", questionText);
      messageInput.placeholder = "Answer the clarification questions to continue...";
      renderAgentActivity(payload.agent_activity || []);
    } else {
      appendMessage("assistant", payload.assistant_message, {
        links: {
          "main.tex": payload.artifact_urls?.main_tex,
          "references.bib": payload.artifact_urls?.references_bib,
          "compile instructions": payload.artifact_urls?.compile_instructions,
          "summary.json": payload.artifact_urls?.summary,
        },
      });
      messageInput.placeholder = "Enter a new research topic...";
    }

    renderInsights(payload);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
  } finally {
    stopGeneratingUI();
  }
});

newSessionBtn.addEventListener("click", () => {
  sessionId = null;
  sessionInfoEl.textContent = "Session: not initialized";
  insightBoxEl.textContent = "No run yet.";
  stopLoadingActivity();
  renderAgentActivity([]);
  appendMessage("assistant", "Started a fresh session. You can send a new topic.");
});

appendMessage("assistant", "Welcome. Enter a research topic to begin.");
renderAgentActivity([]);
