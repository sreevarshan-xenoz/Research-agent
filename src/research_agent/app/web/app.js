const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const templateSelect = document.getElementById("templateSelect");
const languageSelect = document.getElementById("languageSelect");
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
const pdfLinkEl = document.getElementById("pdfLink");
const pipelineSteps = document.querySelectorAll(".pipeline-tracker .step");
const pipelineLines = document.querySelectorAll(".pipeline-tracker .step-line");
const workbenchStatusEl = document.getElementById("workbenchStatus");
const discoveryFeedEl = document.getElementById("discoveryFeed");
const evidenceExplorerEl = document.getElementById("evidenceExplorer");
const docStatusEl = document.getElementById("docStatusEl");
const docProgressBarEl = document.getElementById("docProgressBar");
const copyDocBtn = document.getElementById("copyDocBtn");

// AUTH ELEMENTS
const authOverlayEl = document.getElementById("authOverlay");
const appShellEl = document.querySelector(".app-shell");
const authFormEl = document.getElementById("authForm");
const authEmailEl = document.getElementById("authEmail");
const authPasswordEl = document.getElementById("authPassword");
const authTitleEl = document.getElementById("authTitle");
const authSubmitBtnEl = document.getElementById("authSubmitBtn");
const authToggleBtnEl = document.getElementById("authToggleBtn");
const authToggleTextEl = document.getElementById("authToggleText");

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
let authToken = localStorage.getItem("research_auth_token");
let authMode = "login"; // "login" or "register"

class WebSocketManager {
  constructor() {
    this.ws = null;
    this.onEvent = null;
  }

  async connect(sid, token) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/ws/chat/${sid}?token=${token}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log("WebSocket connected");
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (this.onEvent) this.onEvent(data);
        } catch (e) {
          console.error("WS Parse error:", e);
        }
      };

      this.ws.onclose = () => {
        console.warn("WebSocket closed");
        this.ws = null;
      };

      this.ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        reject(err);
      };
    });
  }

  send(data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected");
    }
    this.ws.send(JSON.stringify(data));
  }
}

const wsManager = new WebSocketManager();

function toggleAuthMode() {
  authMode = authMode === "login" ? "register" : "login";
  authTitleEl.textContent = authMode === "login" ? "Login to your account" : "Create a new account";
  authSubmitBtnEl.textContent = authMode === "login" ? "Login" : "Register";
  authToggleTextEl.innerHTML = authMode === "login" 
    ? 'Don\'t have an account? <a href="#" id="authToggleBtn">Register</a>'
    : 'Already have an account? <a href="#" id="authToggleBtn">Login</a>';
  
  document.getElementById("authToggleBtn").addEventListener("click", (e) => {
    e.preventDefault();
    toggleAuthMode();
  });
}

authToggleBtnEl?.addEventListener("click", (e) => {
  e.preventDefault();
  toggleAuthMode();
});

authFormEl?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = authEmailEl.value;
  const password = authPasswordEl.value;

  try {
    if (authMode === "login") {
      const response = await fetch("/auth/jwt/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password: password }),
      });
      if (!response.ok) throw new Error("Invalid credentials");
      const data = await response.json();
      authToken = data.access_token;
    } else {
      const response = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error("Registration failed");
      authMode = "login";
      authFormEl.dispatchEvent(new Event("submit"));
      return;
    }

    localStorage.setItem("research_auth_token", authToken);
    checkAuth();
  } catch (err) {
    alert(err.message);
  }
});

function checkAuth() {
  if (authToken) {
    authOverlayEl.classList.add("hidden");
    appShellEl.classList.remove("hidden");
    tryResumeSession();
  } else {
    authOverlayEl.classList.remove("hidden");
    appShellEl.classList.add("hidden");
  }
}

function switchWorkbenchTab(tab) {
  const isDoc = tab === "doc";
  if (docTabBtn) docTabBtn.classList.toggle("active", isDoc);
  if (latexTabBtn) latexTabBtn.classList.toggle("active", !isDoc);
  const docPanel = document.querySelector(".doc-panel");
  const latexPanel = document.querySelector(".latex-panel");
  if (docPanel) docPanel.classList.toggle("active", isDoc);
  if (latexPanel) latexPanel.classList.toggle("active", !isDoc);
}

function setDocStatus(status, text) {
  if (!docStatusEl) return;
  const dot = docStatusEl.querySelector(".status-dot");
  const statusText = docStatusEl.querySelector(".status-text") || docStatusEl.parentElement?.querySelector(".status-text");
  if (dot) dot.className = "status-dot " + status;
  if (statusText && text) statusText.textContent = text;
}

function setDocProgress(percent) {
  if (!docProgressBarEl) return;
  const fill = docProgressBarEl.querySelector(".doc-progress-fill");
  if (percent > 0) {
    docProgressBarEl.classList.add("active");
    if (fill) fill.style.width = Math.min(100, percent) + "%";
  } else {
    docProgressBarEl.classList.remove("active");
    if (fill) fill.style.width = "0%";
  }
}

async function copyDocumentToClipboard() {
  if (!quill) return;
  const text = quill.getText();
  try {
    await navigator.clipboard.writeText(text);
    if (copyDocBtn) {
      const originalHTML = copyDocBtn.innerHTML;
      copyDocBtn.innerHTML = 'Copied!';
      setTimeout(() => { copyDocBtn.innerHTML = originalHTML; }, 2000);
    }
  } catch (err) { console.error(err); }
}

function setWorkbenchStatus(status, label) {
  if (!workbenchStatusEl) return;
  const normalized = String(status || "idle").toLowerCase();
  workbenchStatusEl.className = "workbench-status";
  if (["running", "generating", "active"].includes(normalized)) {
    workbenchStatusEl.classList.add("running");
    setDocStatus("running", "Generating...");
  } else if (["ready", "complete", "done", "success"].includes(normalized)) {
    workbenchStatusEl.classList.add("ready");
    setDocStatus("complete", "Complete");
    setDocProgress(100);
  } else if (["error", "failed"].includes(normalized)) {
    workbenchStatusEl.classList.add("error");
    setDocStatus("idle", "Error");
  } else {
    workbenchStatusEl.classList.add("idle");
    setDocStatus("idle", label || normalized);
  }
  workbenchStatusEl.textContent = label || normalized;
}

function updatePipelineTracker(phase) {
  const phaseMap = {
    intake: 0, clarifier: 0, await_user: 0, planner: 1, 
    worker_executor: 2, loop: 2, workers_complete: 2, 
    indexing: 3, critic: 3, await_user_critic: 3, 
    combiner: 4, figure_generator: 4, citation_verifier: 4, 
    composer: 4, exporter: 4, latex_composed: 4, completed: 4
  };
  const currentIndex = phaseMap[phase] ?? -1;
  if (currentIndex === -1) return;
  pipelineSteps.forEach((step, i) => {
    step.classList.remove("active", "complete");
    if (i < currentIndex) step.classList.add("complete");
    else if (i === currentIndex) step.classList.add("active");
  });
  pipelineLines.forEach((line, i) => {
    line.classList.remove("active", "complete");
    if (i < currentIndex) line.classList.add("complete");
    else if (i === currentIndex) line.classList.add("active");
  });
}

function resetWorkbench() {
  if (latexStreamEl) {
    const codeEl = latexStreamEl.querySelector("code");
    if (codeEl) codeEl.textContent = "No generation yet.";
    latexStreamEl.classList.remove("streaming");
  }
  if (quill) quill.setText("Research document will appear here...");
  if (discoveryFeedEl) discoveryFeedEl.innerHTML = '<p class="small muted">Findings will stream here...</p>';
  if (evidenceExplorerEl) evidenceExplorerEl.innerHTML = '<p class="small muted">Evidence links will appear here...</p>';
  if (newOverleafLinkEl) newOverleafLinkEl.href = "https://www.overleaf.com/project/new";
  if (bundleLinkEl) { bundleLinkEl.href = "#"; bundleLinkEl.classList.add("hidden"); }
  if (pdfLinkEl) { pdfLinkEl.href = "#"; pdfLinkEl.classList.add("hidden"); }
  setWorkbenchStatus("idle", "idle");
  updatePipelineTracker("intake");
}

function renderEvidenceExplorer(sectionEvidence) {
  if (!evidenceExplorerEl) return;
  const rows = Array.isArray(sectionEvidence) ? sectionEvidence : [];
  evidenceExplorerEl.innerHTML = "";
  rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "discovery-item fade-in";
    const title = document.createElement("span");
    title.className = "source";
    title.textContent = row.section || "Section";
    item.appendChild(title);
    const details = document.createElement("div");
    details.textContent = `confidence: ${Number.isFinite(row.confidence) ? row.confidence.toFixed(2) : "n/a"}`;
    item.appendChild(details);
    const refs = document.createElement("div");
    refs.className = "small";
    refs.textContent = Array.isArray(row.sources) ? row.sources.slice(0, 4).join(" | ") : "no sources";
    item.appendChild(refs);
    evidenceExplorerEl.appendChild(item);
  });
}

function appendLatexChunk(chunk) {
  if (!chunk || !latexStreamEl) return;
  const codeEl = latexStreamEl.querySelector("code");
  if (!codeEl) return;
  if (codeEl.textContent === "No generation yet." || codeEl.textContent.startsWith("Preparing")) {
    codeEl.textContent = "";
    latexStreamEl.classList.add("typing-active");
  }
  codeEl.textContent += chunk;
  if (typeof Prism !== 'undefined') Prism.highlightElement(codeEl);
  latexStreamEl.scrollTop = latexStreamEl.scrollHeight;
}

function finishLatexChunk() {
  if (latexStreamEl) latexStreamEl.classList.remove("typing-active");
}

function renderDocPreview(htmlContent) {
  if (!quill) return;
  if (!htmlContent || !htmlContent.trim()) {
    quill.setText("Preview unavailable.");
    return;
  }
  quill.root.innerHTML = htmlContent;
}

function applyOverleafUrls(overleafUrls) {
  if (newOverleafLinkEl) newOverleafLinkEl.href = overleafUrls?.new_project || "https://www.overleaf.com/project/new";
  if (bundleLinkEl) {
    if (overleafUrls?.upload_bundle) {
      bundleLinkEl.href = overleafUrls.upload_bundle;
      bundleLinkEl.classList.remove("hidden");
    } else {
      bundleLinkEl.classList.add("hidden");
    }
  }
}

function renderArtifacts(urls) {
  if (!urls) return;
  if (bundleLinkEl && urls.bundle) {
    bundleLinkEl.href = urls.bundle;
    bundleLinkEl.classList.remove("hidden");
  }
  if (pdfLinkEl && urls.pdf) {
    pdfLinkEl.href = urls.pdf;
    pdfLinkEl.classList.remove("hidden");
  }
}

function appendMessage(role, text, options = {}) {
  if (!messagesEl) return;
  const node = document.createElement("article");
  node.className = `message ${role}`;
  if (options.persona) node.classList.add(`persona-${options.persona}`);
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.innerHTML = role === "user" ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>' : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><path d="M12 12L2.1 12.1"/></svg>';
  node.appendChild(avatar);
  const msgContent = document.createElement("div");
  msgContent.className = "message-body";
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "You" : `Research Agent${options.persona ? ' (' + options.persona + ')' : ''}`;
  msgContent.appendChild(meta);
  const textNode = document.createElement("div");
  textNode.className = "text-content";
  if (role === "assistant" && typeof marked !== 'undefined') textNode.innerHTML = marked.parse(text);
  else textNode.textContent = text;
  msgContent.appendChild(textNode);
  if (options.generating) {
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.innerHTML = "<span></span><span></span><span></span>";
    msgContent.appendChild(typing);
  }
  if (options.links) {
    const links = document.createElement("div");
    links.className = "links";
    Object.entries(options.links).filter(([, href]) => Boolean(href)).forEach(([label, href]) => {
      const link = document.createElement("a");
      link.href = href; link.target = "_blank"; link.className = "btn-link"; link.style.marginRight = "8px"; link.textContent = label;
      links.appendChild(link);
    });
    msgContent.appendChild(links);
  }
  node.appendChild(msgContent);
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return node;
}

function renderAgentActivity(entries) {
  if (!agentPanelEl) return;
  agentPanelEl.innerHTML = entries.length ? "" : '<div class="agent-row idle"><span class="agent-name">No active run</span></div>';
  entries.forEach((entry) => {
    const row = document.createElement("div");
    row.className = `agent-row fade-in status-${entry.status}`;
    row.innerHTML = `<div class="agent-row-top" style="display:flex;justify-content:space-between"><span>${entry.name}</span><span class="agent-pill ${entry.status}">${entry.status}</span></div><div class="detail">${entry.detail || ""}</div>`;
    agentPanelEl.appendChild(row);
  });
}

function startGeneratingUI() {
  if (sendBtn) sendBtn.disabled = true;
  loadingMessageNode = appendMessage("assistant", "Orchestrating...", { generating: true });
  setWorkbenchStatus("running", "running");
  switchWorkbenchTab("latex");
}

function stopGeneratingUI() {
  if (sendBtn) sendBtn.disabled = false;
  if (loadingMessageNode) loadingMessageNode.remove();
  loadingMessageNode = null;
}

async function ensureSession() {
  if (sessionId) return sessionId;
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
    body: JSON.stringify({ template: templateSelect?.value || "ieee-2col" }),
  });
  if (!response.ok) { if (response.status === 401) { authToken = null; checkAuth(); } throw new Error("Session failed"); }
  const payload = await response.json();
  sessionId = payload.session_id;
  localStorage.setItem("research_session_id", sessionId);
  return sessionId;
}

async function tryResumeSession() {
  const sid = localStorage.getItem("research_session_id");
  if (!sid) return;
  try {
    const response = await fetch(`/api/session/${sid}/resume`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (response.ok) {
      const payload = await response.json();
      sessionId = sid;
      appendMessage("assistant", "Resumed session.");
      if (templateSelect && payload.template) templateSelect.value = payload.template;
      if (languageSelect && payload.language) languageSelect.value = payload.language;
      const codeEl = latexStreamEl?.querySelector("code");
      if (codeEl && payload.latex_text) { codeEl.textContent = payload.latex_text; Prism.highlightElement(codeEl); }
      renderDocPreview(payload.doc_preview_html);
      renderArtifacts(payload.artifact_urls);
      applyOverleafUrls(payload.overleaf_urls);
      renderEvidenceExplorer(payload.section_evidence);
      setWorkbenchStatus("ready", "success");
      switchWorkbenchTab("doc");
    } else { localStorage.removeItem("research_session_id"); sessionId = null; }
  } catch (err) { console.error(err); }
}

async function sendMessageStream(text, onEvent) {
  const sid = await ensureSession();
  wsManager.onEvent = onEvent;
  await wsManager.connect(sid, authToken);
  wsManager.send({
    action: "chat", message: text,
    template: templateSelect?.value, language: languageSelect?.value,
    depth: depthSelect?.value, autonomy_mode: autonomySelect?.value,
    max_runtime_minutes: Number.parseInt(runtimeCapInput?.value),
    max_cost_usd: Number.parseFloat(costCapInput?.value),
  });
}

chatForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = messageInput?.value.trim();
  if (!text) return;
  appendMessage("user", text);
  messageInput.value = "";
  startGeneratingUI();
  try {
    let payload = null;
    await new Promise((resolve, reject) => {
      sendMessageStream(text, (eventData) => {
        if (eventData.event === "status") {
          if (eventData.payload.phase) updatePipelineTracker(eventData.payload.phase);
          renderAgentActivity(eventData.payload.agent_activity || []);
        } else if (eventData.event === "latex_chunk") {
          appendLatexChunk(eventData.payload.chunk);
        } else if (eventData.event === "result" || eventData.event === "clarification") {
          payload = eventData.payload; resolve();
        } else if (eventData.event === "error") reject(new Error(eventData.payload.message));
      }).catch(reject);
    });
    if (payload.kind === "clarification") {
      appendMessage("assistant", payload.assistant_message, { persona: payload.persona });
    } else {
      appendMessage("assistant", payload.assistant_message, {
        persona: payload.persona,
        links: { "PDF": payload.artifact_urls?.pdf, "Overleaf": payload.overleaf_urls?.new_project }
      });
      const codeEl = latexStreamEl?.querySelector("code");
      if (codeEl && payload.latex_text) { codeEl.textContent = payload.latex_text; Prism.highlightElement(codeEl); }
      renderDocPreview(payload.doc_preview_html);
      renderArtifacts(payload.artifact_urls);
      setWorkbenchStatus("ready", "success");
      updatePipelineTracker("completed");
      switchWorkbenchTab("doc");
    }
  } catch (err) { appendMessage("assistant", `Error: ${err.message}`); setWorkbenchStatus("error", "error"); }
  finally { stopGeneratingUI(); }
});

newSessionBtn?.addEventListener("click", () => {
  sessionId = null; localStorage.removeItem("research_session_id");
  resetWorkbench(); appendMessage("assistant", "Session reset.");
});

stopRunBtn?.addEventListener("click", async () => {
  if (!sessionId) return;
  try {
    if (wsManager.ws?.readyState === WebSocket.OPEN) wsManager.send({ action: "stop" });
    else await fetch(`/api/session/${sessionId}/stop`, { method: "POST", headers: { "Authorization": `Bearer ${authToken}` } });
    appendMessage("assistant", "Stop requested.");
  } catch (err) { console.error(err); }
});

latexTabBtn?.addEventListener("click", () => switchWorkbenchTab("latex"));
docTabBtn?.addEventListener("click", () => switchWorkbenchTab("doc"));
copyDocBtn?.addEventListener("click", copyDocumentToClipboard);

(async () => {
  resetWorkbench();
  checkAuth();
})();
