const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const templateSelect = document.getElementById("templateSelect");
const depthSelect = document.getElementById("depthSelect");
const autonomySelect = document.getElementById("autonomySelect");
const runtimeCapInput = document.getElementById("runtimeCapInput");
const costCapInput = document.getElementById("costCapInput");
const sessionInfoEl = document.getElementById("sessionInfo");
const insightBoxEl = document.getElementById("insightBox");
const newSessionBtn = document.getElementById("newSessionBtn");
const stopRunBtn = document.getElementById("stopRunBtn");
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
const evidenceExplorerEl = document.getElementById("evidenceExplorer");
const docStatusEl = document.getElementById("docStatusEl");
const docProgressBarEl = document.getElementById("docProgressBar");
const copyDocBtn = document.getElementById("copyDocBtn");

// Initialize Quill Editor (if element exists)
let quill = null;
if (docEditorEl) {
  quill = new Quill("#docEditor", {
    theme: "snow",
    modules: {
      toolbar: [
        [{ header: [1, 2, 3, false] }],
        ["bold", "italic", "underline", "strike"],
        [{ list: "ordered" }, { list: "bullet" }],
        [{ 'align': [] }],
        ["clean"],
      ],
    },
  });
}

let sessionId = null;
let loadingMessageNode = null;
let loadingTickerId = null;

function switchWorkbenchTab(tab) {
  const isDoc = tab === "doc";
  
  // Update Buttons
  if (docTabBtn) docTabBtn.classList.toggle("active", isDoc);
  if (latexTabBtn) latexTabBtn.classList.toggle("active", !isDoc);
  
  // Update Panels (Using class-based selection for robustness)
  const docPanel = document.querySelector(".doc-panel");
  const latexPanel = document.querySelector(".latex-panel");
  
  if (docPanel) docPanel.classList.toggle("active", isDoc);
  if (latexPanel) latexPanel.classList.toggle("active", !isDoc);
  
  console.log("Switched to tab:", tab, "isDoc:", isDoc);
}

function setDocStatus(status, text) {
  if (!docStatusEl) return;
  const dot = docStatusEl.querySelector(".status-dot");
  const statusText = docStatusEl.querySelector(".status-text") || docStatusEl.parentElement?.querySelector(".status-text");
  if (dot) {
    dot.className = "status-dot " + status;
  }
  if (statusText && text) {
    statusText.textContent = text;
  }
}

function setDocProgress(percent) {
  if (!docProgressBarEl) return;
  const fill = docProgressBarEl.querySelector(".doc-progress-fill");
  if (percent > 0) {
    docProgressBarEl.classList.add("active");
    if (fill) {
      fill.style.width = Math.min(100, percent) + "%";
    }
  } else {
    docProgressBarEl.classList.remove("active");
    if (fill) {
      fill.style.width = "0%";
    }
  }
}

async function copyDocumentToClipboard() {
  if (!quill) return;
  const text = quill.getText();
  try {
    await navigator.clipboard.writeText(text);
    if (copyDocBtn) {
      const originalHTML = copyDocBtn.innerHTML;
      copyDocBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Copied!';
      setTimeout(() => {
        copyDocBtn.innerHTML = originalHTML;
      }, 2000);
    }
  } catch (err) {
    console.error("Failed to copy:", err);
  }
}

function setWorkbenchStatus(status, label) {
  if (!workbenchStatusEl) return;
  const normalized = String(status || "idle").toLowerCase();
  workbenchStatusEl.className = "workbench-status";
  if (["running", "generating", "active"].includes(normalized)) {
    workbenchStatusEl.classList.add("running");
    setDocStatus("running", "Generating content...");
  } else if (["ready", "complete", "completed", "done", "success"].includes(normalized)) {
    workbenchStatusEl.classList.add("ready");
    setDocStatus("complete", "Content complete");
    setDocProgress(100);
  } else if (["error", "failed", "blocked"].includes(normalized)) {
    workbenchStatusEl.classList.add("error");
    setDocStatus("idle", "Error");
  } else {
    workbenchStatusEl.classList.add("idle");
    setDocStatus("idle", label || normalized);
  }
  workbenchStatusEl.textContent = label || normalized;
}

function resetWorkbench() {
  if (latexStreamEl) {
    latexStreamEl.textContent = "No generation yet.";
    latexStreamEl.classList.remove("streaming");
  }
  if (quill) {
    quill.setText("Research document will appear here after generation...");
  }
  if (discoveryFeedEl) {
    discoveryFeedEl.innerHTML = '<p class="small muted">Findings will stream here...</p>';
  }
  if (evidenceExplorerEl) {
    evidenceExplorerEl.innerHTML = '<p class="small muted">Section evidence links will appear after generation...</p>';
  }
  if (newOverleafLinkEl) newOverleafLinkEl.href = "https://www.overleaf.com/project/new";
  if (bundleLinkEl) {
    bundleLinkEl.href = "#";
    bundleLinkEl.classList.add("hidden");
  }
  setWorkbenchStatus("idle", "idle");
  switchWorkbenchTab("doc");
}

function renderEvidenceExplorer(sectionEvidence) {
  if (!evidenceExplorerEl) return;

  const rows = Array.isArray(sectionEvidence) ? sectionEvidence : [];
  if (!rows.length) {
    evidenceExplorerEl.innerHTML = '<p class="small muted">No section evidence available for this run.</p>';
    return;
  }

  evidenceExplorerEl.innerHTML = "";
  rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "discovery-item fade-in";

    const title = document.createElement("span");
    title.className = "source";
    title.textContent = row.section || "Section";
    item.appendChild(title);

    const details = document.createElement("div");
    const confidence = Number.isFinite(row.confidence) ? row.confidence.toFixed(2) : "n/a";
    details.textContent = `confidence: ${confidence}`;
    item.appendChild(details);

    const refs = document.createElement("div");
    refs.className = "small";
    const labels = Array.isArray(row.sources) ? row.sources.slice(0, 4).join(" | ") : "no sources";
    refs.textContent = labels || "no sources";
    item.appendChild(refs);

    evidenceExplorerEl.appendChild(item);
  });
}

function appendLatexChunk(chunk) {
  if (!chunk || !latexStreamEl) return;
  if (
    latexStreamEl.textContent === "No generation yet." ||
    latexStreamEl.textContent.startsWith("Preparing") ||
    latexStreamEl.textContent.startsWith("Waiting")
  ) {
    latexStreamEl.textContent = "";
    latexStreamEl.classList.add("typing-active");
  }
  latexStreamEl.textContent += chunk;
  latexStreamEl.scrollTop = latexStreamEl.scrollHeight;
}

function finishLatexChunk() {
  if (latexStreamEl) {
    latexStreamEl.classList.remove("typing-active");
  }
}

function renderDocPreview(htmlContent) {
  if (!quill) return;
  if (!htmlContent || !htmlContent.trim()) {
    quill.setText("Document preview is not available for this run.");
    return;
  }
  // Use root.innerHTML to inject the formatted HTML from backend
  quill.root.innerHTML = htmlContent;
}

function applyOverleafUrls(overleafUrls) {
  const projectLink = overleafUrls?.new_project || "https://www.overleaf.com/project/new";
  if (newOverleafLinkEl) newOverleafLinkEl.href = projectLink;

  const bundleLink = overleafUrls?.upload_bundle;
  if (bundleLinkEl) {
    if (bundleLink) {
      bundleLinkEl.href = bundleLink;
      bundleLinkEl.classList.remove("hidden");
    } else {
      bundleLinkEl.href = "#";
      bundleLinkEl.classList.add("hidden");
    }
  }
}

function appendMessage(role, text, options = {}) {
  if (!messagesEl) return;
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
        link.className = "btn-link";
        link.style.marginTop = "8px";
        link.style.marginRight = "8px";
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
  if (!discoveryFeedEl || !detail || detail.includes("Planned") || detail.includes("scored") || detail.includes("Initial")) return;
  
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
  if (!agentPanelEl) return;
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
  if (sendBtn) sendBtn.disabled = true;
  if (messageInput) messageInput.disabled = true;
  loadingMessageNode = appendMessage("assistant", "Orchestrating research flow...", {
    generating: true,
  });
  if (latexStreamEl) {
    latexStreamEl.textContent = "Waiting for agent stream...";
    latexStreamEl.classList.add("streaming");
  }
  setDocStatus("running", "Orchestrating research...");
  setDocProgress(5);
  setWorkbenchStatus("running", "running");
  switchWorkbenchTab("latex");
  startLoadingActivity();
}

function stopGeneratingUI() {
  if (sendBtn) sendBtn.disabled = false;
  if (messageInput) messageInput.disabled = false;
  stopLoadingActivity();
  finishLatexChunk();
  if (loadingMessageNode && loadingMessageNode.parentElement) {
    loadingMessageNode.parentElement.removeChild(loadingMessageNode);
  }
  loadingMessageNode = null;
  if (latexStreamEl) latexStreamEl.classList.remove("streaming");
}

async function ensureSession() {
  if (sessionId) return sessionId;

  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template: templateSelect?.value || "ieee-2col" }),
  });

  if (!response.ok) throw new Error("Failed to initialize research session.");

  const payload = await response.json();
  sessionId = payload.session_id;
  if (sessionInfoEl) sessionInfoEl.textContent = `Session: ${sessionId}`;
  return sessionId;
}

function renderInsights(payload) {
  if (!insightBoxEl) return;
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
  const runtimeCap = Number.parseInt(runtimeCapInput?.value || "25", 10);
  const costCap = Number.parseFloat(costCapInput?.value || "5.0");
  let response;
  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sid,
        message: text,
        template: templateSelect?.value || "ieee-2col",
        depth: depthSelect?.value || "balanced",
        autonomy_mode: autonomySelect?.value || "hybrid",
        max_runtime_minutes: Number.isFinite(runtimeCap) ? Math.max(1, runtimeCap) : 25,
        max_cost_usd: Number.isFinite(costCap) ? Math.max(0, costCap) : 5.0,
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
      let event;
      try {
        event = JSON.parse(trimmed);
      } catch (e) {
        console.error("Stream parse error", e);
        continue;
      }
      onEvent(event);
    }
  }

  if (pending.trim()) {
    try {
      const event = JSON.parse(pending.trim());
      onEvent(event);
    } catch (e) {
      console.error("Stream parse error", e);
    }
  }
}

chatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput?.value.trim();
  if (!text) return;

  appendMessage("user", text);
  if (messageInput) messageInput.value = "";
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
      if (messageInput) messageInput.placeholder = "Please clarify details above...";
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
      if (messageInput) messageInput.placeholder = "Enter a new topic...";
      if (payload.latex_text && latexStreamEl) {
        latexStreamEl.textContent = payload.latex_text;
      }
      renderDocPreview(payload.doc_preview_html || "");
      applyOverleafUrls(payload.overleaf_urls || {});
      renderEvidenceExplorer(payload.section_evidence || []);
      
      // FINISH RUN UI
      setWorkbenchStatus("ready", "success");
      switchWorkbenchTab("doc"); // AUTO SWITCH TO DOC VIEW
      
      // Optional: show a small toast or pulse the tab
      docTabBtn.classList.add("pulse");
      setTimeout(() => docTabBtn.classList.remove("pulse"), 2000);
    }

    renderInsights(payload);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
    setWorkbenchStatus("error", "error");
  } finally {
    stopGeneratingUI();
  }
});

newSessionBtn?.addEventListener("click", () => {
  sessionId = null;
  if (sessionInfoEl) sessionInfoEl.textContent = "Session: not initialized";
  if (insightBoxEl) insightBoxEl.textContent = "No run yet.";
  stopLoadingActivity();
  renderAgentActivity([]);
  resetWorkbench();
  appendMessage("assistant", "Session reset. Ready for new topic.");
});

stopRunBtn?.addEventListener("click", async () => {
  if (!sessionId) {
    appendMessage("assistant", "No active session to stop.");
    return;
  }

  try {
    const response = await fetch(`/api/session/${sessionId}/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const payload = await response.json();
    if (response.ok && payload?.ok) {
      appendMessage("assistant", "Stop request sent. Wrapping up current run...");
      setWorkbenchStatus("waiting", "stopping");
    } else {
      appendMessage("assistant", `Stop request failed: ${payload?.detail || "unknown error"}`);
    }
  } catch (error) {
    appendMessage("assistant", `Stop request failed: ${error.message}`);
  }
});

latexTabBtn?.addEventListener("click", () => switchWorkbenchTab("latex"));
docTabBtn?.addEventListener("click", () => switchWorkbenchTab("doc"));
copyDocBtn?.addEventListener("click", copyDocumentToClipboard);

appendMessage("assistant", "Welcome. I am your Research Agent. Enter a topic to start.");
renderAgentActivity([]);
resetWorkbench();
