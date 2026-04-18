const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const templateSelect = document.getElementById("templateSelect");
const sessionInfoEl = document.getElementById("sessionInfo");
const insightBoxEl = document.getElementById("insightBox");
const newSessionBtn = document.getElementById("newSessionBtn");
const sendBtn = document.getElementById("sendBtn");
const agentPanelEl = document.getElementById("agentPanel");
const latexTabBtn = document.getElementById("latexTabBtn");
const docTabBtn = document.getElementById("docTabBtn");
const latexWorkbenchEl = document.getElementById("latexWorkbench");
const docWorkbenchEl = document.getElementById("docWorkbench");
const latexStreamEl = document.getElementById("latexStream");
const docEditorEl = document.getElementById("docEditor");
const newOverleafLinkEl = document.getElementById("newOverleafLink");
const bundleLinkEl = document.getElementById("bundleLink");
const workbenchStatusEl = document.getElementById("workbenchStatus");
const discoveryFeedEl = document.getElementById("discoveryFeed");

// Initialize Quill Editor
const quill = new Quill("#docEditor", {
  theme: "snow",
  modules: {
    toolbar: [
      [{ header: [1, 2, 3, false] }],
      ["bold", "italic", "underline", "strike"],
      [{ list: "ordered" }, { list: "bullet" }],
      ["clean"],
    ],
  },
});

let sessionId = null;
let loadingMessageNode = null;
let loadingTickerId = null;

function switchWorkbenchTab(tab) {
  const isDoc = tab === "doc";
  docTabBtn.classList.toggle("active", isDoc);
  latexTabBtn.classList.toggle("active", !isDoc);
  docWorkbenchEl.classList.toggle("active", isDoc);
  latexWorkbenchEl.classList.toggle("active", !isDoc);
}

function setWorkbenchStatus(status, label) {
  const normalized = String(status || "idle").toLowerCase();
  workbenchStatusEl.className = "workbench-status";
  if (["running", "generating", "active"].includes(normalized)) {
    workbenchStatusEl.classList.add("running");
  } else if (["ready", "complete", "completed", "done", "success"].includes(normalized)) {
    workbenchStatusEl.classList.add("ready");
  } else if (["error", "failed", "blocked"].includes(normalized)) {
    workbenchStatusEl.classList.add("error");
  } else {
    workbenchStatusEl.classList.add("idle");
  }
  workbenchStatusEl.textContent = label || normalized;
}

function resetWorkbench() {
  latexStreamEl.textContent = "No generation yet.";
  latexStreamEl.classList.remove("streaming");
  quill.setText("Research document will appear here after generation...");
  discoveryFeedEl.innerHTML = '<p class="small muted">Findings will stream here...</p>';
  newOverleafLinkEl.href = "https://www.overleaf.com/project/new";
  bundleLinkEl.href = "#";
  bundleLinkEl.classList.add("hidden");
  setWorkbenchStatus("idle", "idle");
  switchWorkbenchTab("doc");
}

function appendLatexChunk(chunk) {
  if (!chunk) return;
  if (
    latexStreamEl.textContent === "No generation yet." ||
    latexStreamEl.textContent.startsWith("Preparing")
  ) {
    latexStreamEl.textContent = "";
  }
  latexStreamEl.textContent += chunk;
  latexStreamEl.scrollTop = latexStreamEl.scrollHeight;
}

function renderDocPreview(htmlContent) {
  if (!htmlContent || !htmlContent.trim()) {
    quill.setText("Document preview is not available for this run.");
    return;
  }
  quill.root.innerHTML = htmlContent;
}

function applyOverleafUrls(overleafUrls) {
  const projectLink = overleafUrls?.new_project || "https://www.overleaf.com/project/new";
  newOverleafLinkEl.href = projectLink;

  const bundleLink = overleafUrls?.upload_bundle;
  if (bundleLink) {
    bundleLinkEl.href = bundleLink;
    bundleLinkEl.classList.remove("hidden");
  } else {
    bundleLinkEl.href = "#";
    bundleLinkEl.classList.add("hidden");
  }
}

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
  if (["complete", "completed", "done", "success"].includes(normalized)) return "complete";
  if (["running", "in_progress", "executing", "active"].includes(normalized)) return "running";
  if (["waiting", "awaiting_user_clarification", "clarification"].includes(normalized)) return "waiting";
  if (["blocked", "error", "failed"].includes(normalized)) return "error";
  if (["pending"].includes(normalized)) return "pending";
  return "idle";
}

function appendDiscovery(agent, detail) {
  if (!detail || detail.includes("Planned") || detail.includes("scored") || detail.includes("Initial")) return;
  
  // Clear initial placeholder
  if (discoveryFeedEl.querySelector(".muted")) {
    discoveryFeedEl.innerHTML = "";
  }

  const item = document.createElement("div");
  item.className = "discovery-item fade-in";
  
  const source = document.createElement("span");
  source.className = "source";
  source.textContent = agent;
  
  const text = document.createElement("div");
  text.textContent = detail;
  
  item.appendChild(source);
  item.appendChild(text);
  discoveryFeedEl.prepend(item); // Show newest at top
}

function renderAgentActivity(entries) {
  const safeEntries = Array.isArray(entries) ? entries : [];
  if (!safeEntries.length) {
    agentPanelEl.innerHTML = `
      <div class="agent-row idle">
        <div class="agent-row-top" style="display: flex; justify-content: space-between; align-items: center;">
          <span class="agent-name">No active run</span>
          <span class="agent-pill idle">idle</span>
        </div>
      </div>`;
    return;
  }

  agentPanelEl.innerHTML = "";
  safeEntries.forEach((entry) => {
    const status = normalizeStatus(entry.status);
    const row = document.createElement("div");
    row.className = `agent-row fade-in status-${status}`;

    const name = document.createElement("span");
    name.className = "agent-name";
    name.textContent = entry.name || "Agent";

    const pill = document.createElement("span");
    pill.className = `agent-pill ${status}`;
    pill.textContent = status;

    const top = document.createElement("div");
    top.className = "agent-row-top";
    top.style.display = "flex";
    top.style.justifyContent = "space-between";
    top.style.alignItems = "center";
    top.appendChild(name);
    top.appendChild(pill);

    row.appendChild(top);

    if (entry.detail) {
      const detail = document.createElement("div");
      detail.className = "detail";
      detail.textContent = entry.detail;
      row.appendChild(detail);
      
      // Smart Buffering: Add to discovery feed if it's research data
      if (status === "complete" || status === "running") {
         appendDiscovery(entry.name, entry.detail);
      }
    }

    agentPanelEl.appendChild(row);
  });

  agentPanelEl.scrollTop = agentPanelEl.scrollHeight;
}

function startLoadingActivity() {
  stopLoadingActivity();
  renderAgentActivity([
    {
      name: "Orchestrator",
      status: "running",
      detail: "Initializing pipeline...",
    },
  ]);
}

function stopLoadingActivity() {
  if (!loadingTickerId) return;
  window.clearInterval(loadingTickerId);
  loadingTickerId = null;
}

function startGeneratingUI() {
  sendBtn.disabled = true;
  messageInput.disabled = true;
  loadingMessageNode = appendMessage("assistant", "Orchestrating research flow...", {
    generating: true,
  });
  latexStreamEl.textContent = "Waiting for agent stream...";
  latexStreamEl.classList.add("streaming");
  setWorkbenchStatus("running", "running");
  switchWorkbenchTab("latex");
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
  latexStreamEl.classList.remove("streaming");
}

async function ensureSession() {
  if (sessionId) return sessionId;

  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template: templateSelect.value }),
  });

  if (!response.ok) throw new Error("Failed to initialize research session.");

  const payload = await response.json();
  sessionId = payload.session_id;
  sessionInfoEl.textContent = `Session: ${sessionId}`;
  return sessionId;
}

function renderInsights(payload) {
  if (payload.kind !== "result") {
    insightBoxEl.textContent = "Clarification active.";
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
    "Confidence Scores:",
    confidence || "n/a",
    "",
    "Critic Review:",
    notes,
    "",
    "Warnings:",
    warnings,
  ].join("\n");

  renderAgentActivity(payload.agent_activity || []);
}

async function sendMessageStream(text, onEvent) {
  const sid = await ensureSession();
  let response;
  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sid,
        message: text,
        template: templateSelect.value,
      }),
    });
  } catch (err) {
    throw new Error(`Connection failed: ${err.message}`);
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Server error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("Stream reader not available.");

  const decoder = new TextDecoder();
  let pending = "";

  while (true) {
    let result;
    try {
      result = await reader.read();
    } catch (err) {
      throw new Error(`Stream read error: ${err.message}`);
    }

    const { value, done } = result;
    if (done) break;

    pending += decoder.decode(value, { stream: true });
    const lines = pending.split("\n");
    pending = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const event = JSON.parse(trimmed);
        onEvent(event);
      } catch (e) {
        console.error("Stream parse error", e);
      }
    }
  }

  if (pending.trim()) {
    try {
      onEvent(JSON.parse(pending.trim()));
    } catch (e) {}
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  messageInput.value = "";
  startGeneratingUI();

  try {
    let payload = null;

    await sendMessageStream(text, (eventData) => {
      const eventName = eventData?.event;
      const eventPayload = eventData?.payload || {};

      if (eventName === "status") {
        setWorkbenchStatus("running", "running");
        renderAgentActivity(eventPayload.agent_activity || []);
        return;
      }

      if (eventName === "latex_chunk") {
        appendLatexChunk(eventPayload.chunk || "");
        return;
      }

      if (eventName === "clarification" || eventName === "result") {
        payload = eventPayload;
        return;
      }

      if (eventName === "error") {
        throw new Error(eventPayload.message || "Pipeline error");
      }
    });

    if (!payload) throw new Error("Connection closed without response.");

    if (payload.kind === "clarification") {
      const questionText = [payload.assistant_message, "", ...(payload.questions || []).map((q, i) => `${i + 1}. ${q}`)].join("\n");
      appendMessage("assistant", questionText);
      messageInput.placeholder = "Please clarify details above...";
      renderAgentActivity(payload.agent_activity || []);
      setWorkbenchStatus("waiting", "clarification");
    } else {
      appendMessage("assistant", payload.assistant_message, {
        links: {
          "main.tex": payload.artifact_urls?.main_tex,
          "references.bib": payload.artifact_urls?.references_bib,
          "compile instructions": payload.artifact_urls?.compile_instructions,
          "summary.json": payload.artifact_urls?.summary,
          "overleaf project": payload.overleaf_urls?.new_project,
          "overleaf bundle": payload.overleaf_urls?.upload_bundle,
        },
      });
      messageInput.placeholder = "Enter a new topic...";
      if (payload.latex_text) {
        latexStreamEl.textContent = payload.latex_text;
      }
      renderDocPreview(payload.doc_preview_html || "");
      applyOverleafUrls(payload.overleaf_urls || {});
      setWorkbenchStatus("ready", "ready");
      switchWorkbenchTab("doc");
    }

    renderInsights(payload);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
    setWorkbenchStatus("error", "error");
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
  resetWorkbench();
  appendMessage("assistant", "Session reset. Ready for new topic.");
});

latexTabBtn.addEventListener("click", () => switchWorkbenchTab("latex"));
docTabBtn.addEventListener("click", () => switchWorkbenchTab("doc"));

appendMessage("assistant", "Welcome. I am your Research Agent. Enter a topic to start.");
renderAgentActivity([]);
resetWorkbench();
