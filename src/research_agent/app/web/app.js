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
const previewTabBtn = document.getElementById("previewTabBtn");
const blogTabBtn = document.getElementById("blogTabBtn");
const latexWorkbenchEl = document.getElementById("latexWorkbench");
const docWorkbenchEl = document.getElementById("docWorkbench");
const previewWorkbenchEl = document.getElementById("previewWorkbench");
const blogWorkbenchEl = document.getElementById("blogWorkbench");
const latexStreamEl = document.getElementById("latexStream");
const docEditorEl = document.getElementById("docEditor");
const newOverleafLinkEl = document.getElementById("newOverleafLink");
const bundleLinkEl = document.getElementById("bundleLink");
const pdfLinkEl = document.getElementById("pdfLink");
const overleafPushBtn = document.getElementById("overleafPushBtn");
const overleafPullBtn = document.getElementById("overleafPullBtn");

// Preview Elements
const renderPdfBtn = document.getElementById("renderPdfBtn");
const renderStatusText = document.getElementById("renderStatusText");
const pdfPreviewIframe = document.getElementById("pdfPreviewIframe");
const pdfPlaceholder = document.getElementById("pdfPlaceholder");

// Blog & Social Elements
const generateBlogBtn = document.getElementById("generateBlogBtn");
const blogStatusText = document.getElementById("blogStatusText");
const blogSubTabBtn = document.getElementById("blogSubTabBtn");
const newsletterSubTabBtn = document.getElementById("newsletterSubTabBtn");
const twitterSubTabBtn = document.getElementById("twitterSubTabBtn");
const blogContentArea = document.getElementById("blogContentArea");
const copyBlogContentBtn = document.getElementById("copyBlogContentBtn");

// Multi-mode Elements
const surveyConfigBlock = document.getElementById("surveyConfigBlock");
const libraryConfigBlock = document.getElementById("libraryConfigBlock");
const surveyNumTopics = document.getElementById("surveyNumTopics");
const pdfUploadInput = document.getElementById("pdfUploadInput");
const uploadStatusText = document.getElementById("uploadStatusText");
const librarySelect = document.getElementById("librarySelect");
const runModeRadios = document.querySelectorAll('input[name="runMode"]');



// Overleaf Push Modal
const overleafModal = document.getElementById("overleafModal");
const overleafModalClose = document.getElementById("overleafModalClose");
const overleafModalCancel = document.getElementById("overleafModalCancel");
const overleafModalConfirm = document.getElementById("overleafModalConfirm");
const overleafGitFields = document.getElementById("overleafGitFields");
const overleafGitUrl = document.getElementById("overleafGitUrl");
const overleafGitToken = document.getElementById("overleafGitToken");
const overleafPushStatus = document.getElementById("overleafPushStatus");
const overleafPushStatusText = document.getElementById("overleafPushStatusText");
const overleafPushResult = document.getElementById("overleafPushResult");
const overleafMethodRadios = document.querySelectorAll('input[name="overleafMethod"]');

// Overleaf Pull Modal
const overleafPullModal = document.getElementById("overleafPullModal");
const overleafPullModalClose = document.getElementById("overleafPullModalClose");
const overleafPullModalCancel = document.getElementById("overleafPullModalCancel");
const overleafPullModalConfirm = document.getElementById("overleafPullModalConfirm");
const overleafPullGitUrl = document.getElementById("overleafPullGitUrl");
const overleafPullGitToken = document.getElementById("overleafPullGitToken");
const overleafPullStatus = document.getElementById("overleafPullStatus");
const overleafPullStatusText = document.getElementById("overleafPullStatusText");
const overleafPullResult = document.getElementById("overleafPullResult");
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
let currentRunId = null;
let loadingMessageNode = null;
let loadingTickerId = null;
let authToken = localStorage.getItem("research_auth_token");
let authMode = "login"; // "login" or "register"
let blogData = null;
let activeBlogSubTab = "blog";


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
  if (docTabBtn) docTabBtn.classList.toggle("active", tab === "doc");
  if (latexTabBtn) latexTabBtn.classList.toggle("active", tab === "latex");
  if (previewTabBtn) previewTabBtn.classList.toggle("active", tab === "preview");
  if (blogTabBtn) blogTabBtn.classList.toggle("active", tab === "blog");

  const docPanel = document.querySelector(".doc-panel");
  const latexPanel = document.querySelector(".latex-panel");
  const previewPanel = document.querySelector(".preview-panel");
  const blogPanel = document.querySelector(".blog-panel");

  if (docPanel) docPanel.classList.toggle("active", tab === "doc");
  if (latexPanel) latexPanel.classList.toggle("active", tab === "latex");
  if (previewPanel) previewPanel.classList.toggle("active", tab === "preview");
  if (blogPanel) blogPanel.classList.toggle("active", tab === "blog");
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
  if (newOverleafLinkEl) {
    newOverleafLinkEl.href = "#";
    newOverleafLinkEl.classList.add("hidden");
    newOverleafLinkEl.textContent = "Open Overleaf";
  }
  if (overleafPushBtn) overleafPushBtn.classList.add("hidden");
  if (overleafPullBtn) overleafPullBtn.classList.add("hidden");
  if (bundleLinkEl) { bundleLinkEl.href = "#"; bundleLinkEl.classList.add("hidden"); }
  if (pdfLinkEl) { pdfLinkEl.href = "#"; pdfLinkEl.classList.add("hidden"); }
  currentRunId = null;
  setWorkbenchStatus("idle", "idle");
  updatePipelineTracker("intake");

  // Reset PDF render preview elements
  if (pdfPreviewIframe) {
    pdfPreviewIframe.src = "";
    pdfPreviewIframe.classList.add("hidden");
  }
  if (pdfPlaceholder) pdfPlaceholder.classList.remove("hidden");
  if (renderStatusText) renderStatusText.textContent = "";

  // Reset Blog Export elements
  blogData = null;
  activeBlogSubTab = "blog";
  if (blogContentArea) blogContentArea.textContent = "No content generated yet. Click \"Generate Blog & Social\".";
  if (blogStatusText) blogStatusText.textContent = "";
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
  if (newOverleafLinkEl) {
    if (overleafUrls?.new_project) {
      newOverleafLinkEl.href = overleafUrls.new_project;
      newOverleafLinkEl.classList.remove("hidden");
    } else {
      newOverleafLinkEl.classList.add("hidden");
    }
  }
  if (overleafPushBtn) overleafPushBtn.classList.remove("hidden");
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
  const colPending = document.getElementById("col-pending");
  const colRunning = document.getElementById("col-running");
  const colComplete = document.getElementById("col-complete");
  const countPending = document.getElementById("count-pending");
  const countRunning = document.getElementById("count-running");
  const countComplete = document.getElementById("count-complete");

  if (!colPending || !colRunning || !colComplete) return;

  colPending.innerHTML = "";
  colRunning.innerHTML = "";
  colComplete.innerHTML = "";

  let nPending = 0, nRunning = 0, nComplete = 0;

  entries.forEach((entry) => {
    const status = normalizeStatus(entry.status);
    const row = document.createElement("div");
    row.className = `agent-row status-${status}`;
    row.innerHTML = `
      <div class="agent-row-top">
        <span class="agent-name" title="${entry.name}">${entry.name}</span>
      </div>
      <div class="detail">${entry.detail || ""}</div>
    `;

    if (status === "pending") {
      colPending.appendChild(row);
      nPending++;
    } else if (status === "running" || status === "waiting") {
      colRunning.appendChild(row);
      nRunning++;
    } else {
      colComplete.appendChild(row);
      nComplete++;
    }

    if (status === "running" || status === "complete") {
      appendDiscovery(entry.name, entry.detail);
    }
  });

  if (countPending) countPending.textContent = nPending;
  if (countRunning) countRunning.textContent = nRunning;
  if (countComplete) countComplete.textContent = nComplete;

  // Horizontal scroll to Active if it has items
  if (nRunning > 0) {
     const board = document.getElementById("agentPanel");
     if (board) board.scrollLeft = 200; // Rough estimate to center 'Active'
  }
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
      currentRunId = payload.run_id || null;
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
// Mode Toggle Handlers
runModeRadios.forEach(radio => {
  radio.addEventListener("change", (e) => {
    const mode = e.target.value;
    surveyConfigBlock?.classList.toggle("hidden", mode !== "survey");
    libraryConfigBlock?.classList.toggle("hidden", mode !== "chat");
    
    if (mode === "paper") {
      messageInput.placeholder = "Enter a research topic...";
    } else if (mode === "survey") {
      messageInput.placeholder = "Enter a broad research area to survey...";
    } else if (mode === "chat") {
      messageInput.placeholder = "Ask a question about the active document...";
      loadUserLibraries();
    }
  });
});

async function loadUserLibraries() {
  try {
    const res = await fetch("/api/chat/library", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    if (librarySelect && data.libraries) {
      librarySelect.innerHTML = '<option value="">Select an indexed document</option>';
      data.libraries.forEach(lib => {
        const opt = document.createElement("option");
        opt.value = lib.library_id;
        opt.textContent = `${lib.title || "Untitled"} (${lib.doc_count} docs)`;
        librarySelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Failed to load libraries:", err);
  }
}

pdfUploadInput?.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  
  if (uploadStatusText) uploadStatusText.textContent = "Uploading & indexing...";
  const formData = new FormData();
  formData.append("file", file);
  
  try {
    const res = await fetch("/api/chat/upload", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`
      },
      body: formData
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Upload failed.");
    }
    if (uploadStatusText) uploadStatusText.textContent = "Indexed successfully!";
    await loadUserLibraries();
    if (librarySelect && data.library_id) {
      librarySelect.value = data.library_id;
    }
  } catch (err) {
    if (uploadStatusText) uploadStatusText.textContent = `Upload failed: ${err.message}`;
    console.error(err);
  }
});

async function runSurveyFlow(topic) {
  const numTopics = Number.parseInt(surveyNumTopics?.value) || 5;
  startGeneratingUI();
  setWorkbenchStatus("running", "survey planning");
  updatePipelineTracker("intake");
  try {
    const res = await fetch("/api/survey", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ topic, num_topics: numTopics })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Survey generation failed.");
    }
    currentRunId = data.run_id || null;
    if (currentRunId && overleafPushBtn) overleafPushBtn.classList.remove("hidden");
    if (currentRunId && overleafPullBtn) overleafPullBtn.classList.remove("hidden");
    
    renderDocPreview(
      `<h1>Literature Survey: ${data.topic}</h1>` +
      `<p><strong>Sub-topics:</strong> ${data.sub_topics.map(t => t.name).join(", ")}</p>` +
      `<hr/>` +
      `<h2>Timeline</h2><div style="font-family: monospace; white-space: pre-wrap; font-size: 0.9em; line-height: 1.5;">${data.timeline}</div><hr/>` +
      `<h2>Taxonomy</h2><div style="font-family: monospace; white-space: pre-wrap; font-size: 0.9em; line-height: 1.5;">${data.taxonomy_table}</div><hr/>` +
      `<h2>Research Landscape</h2><div style="font-family: monospace; white-space: pre-wrap; font-size: 0.9em; line-height: 1.5;">${data.research_landscape}</div><hr/>` +
      `<h2>Survey Paper</h2><div>${data.survey}</div>`
    );
    
    const codeEl = latexStreamEl?.querySelector("code");
    if (codeEl && data.survey) {
      codeEl.textContent = data.survey;
      if (typeof Prism !== 'undefined') Prism.highlightElement(codeEl);
    }
    
    appendMessage("assistant", `Multi-paper survey on "${data.topic}" generated successfully. Collected and synthesized findings from ${data.paper_count} papers across ${data.sub_topics.length} sub-topics in ${data.duration_seconds.toFixed(0)} seconds.`);
    setWorkbenchStatus("ready", "success");
    updatePipelineTracker("completed");
    switchWorkbenchTab("doc");
  } catch (err) {
    appendMessage("assistant", `Survey generation failed: ${err.message}`);
    setWorkbenchStatus("error", "error");
  } finally {
    stopGeneratingUI();
  }
}

async function runLibraryChatFlow(question) {
  const libraryId = librarySelect?.value;
  if (!libraryId) {
    appendMessage("assistant", "Please upload a PDF document and select it in the dropdown first.");
    return;
  }
  startGeneratingUI();
  try {
    const res = await fetch("/api/chat/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ library_id: libraryId, question })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Q&A request failed.");
    }
    appendMessage("assistant", data.answer || data.response || "No response received.");
  } catch (err) {
    appendMessage("assistant", `Q&A failed: ${err.message}`);
  } finally {
    stopGeneratingUI();
  }
}

chatForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = messageInput?.value.trim();
  if (!text) return;
  appendMessage("user", text);
  messageInput.value = "";

  const activeMode = document.querySelector('input[name="runMode"]:checked')?.value || "paper";
  if (activeMode === "survey") {
    await runSurveyFlow(text);
  } else if (activeMode === "chat") {
    await runLibraryChatFlow(text);
  } else {
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
          } else if (eventData.event === "result" || eventData.event === "clarification" || eventData.event === "critic_feedback") {
            payload = eventData.payload; resolve();
          } else if (eventData.event === "error") reject(new Error(eventData.payload.message));
        }).catch(reject);
      });
      if (payload.kind === "clarification") {
        appendMessage("assistant", payload.assistant_message, { persona: payload.persona });
        messageInput.placeholder = "Please clarify details...";
        setWorkbenchStatus("waiting", "clarification");
      } else if (payload.kind === "critic_feedback") {
        appendMessage("assistant", payload.assistant_message, { persona: payload.persona });
        messageInput.placeholder = "Provide guidance to the agent...";
        setWorkbenchStatus("waiting", "critic review");
      } else {
        appendMessage("assistant", payload.assistant_message, {
          persona: payload.persona,
          links: { "PDF": payload.artifact_urls?.pdf, "Overleaf": payload.overleaf_urls?.new_project }
        });
        messageInput.placeholder = "Enter a new research topic...";
        currentRunId = payload.run_id || null;
        if (currentRunId && overleafPushBtn) overleafPushBtn.classList.remove("hidden");
        if (currentRunId && overleafPullBtn) overleafPullBtn.classList.remove("hidden");
        const codeEl = latexStreamEl?.querySelector("code");
        if (codeEl && payload.latex_text) { codeEl.textContent = payload.latex_text; Prism.highlightElement(codeEl); }
        renderDocPreview(payload.doc_preview_html);
        renderArtifacts(payload.artifact_urls);
        setWorkbenchStatus("ready", "success");
        updatePipelineTracker("completed");
        switchWorkbenchTab("doc");
      }
    } catch (err) {
      appendMessage("assistant", `Error: ${err.message}`);
      setWorkbenchStatus("error", "error");
    } finally {
      stopGeneratingUI();
    }
  }
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
previewTabBtn?.addEventListener("click", () => switchWorkbenchTab("preview"));
blogTabBtn?.addEventListener("click", () => switchWorkbenchTab("blog"));
copyDocBtn?.addEventListener("click", copyDocumentToClipboard);

// Preview PDF Handlers
renderPdfBtn?.addEventListener("click", () => {
  compilePdfForRun(currentRunId);
});

async function compilePdfForRun(runId) {
  if (!runId) {
    alert("Please run a research topic first.");
    return;
  }
  if (renderPdfBtn) renderPdfBtn.disabled = true;
  if (renderStatusText) renderStatusText.textContent = "Compiling LaTeX to PDF...";
  try {
    const res = await fetch(`/api/runs/${runId}/render`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`
      }
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "PDF compilation failed.");
    }
    if (data.status === "compiled" || data.pdf_path) {
      if (renderStatusText) renderStatusText.textContent = "PDF Rendered successfully!";
      if (pdfPreviewIframe) {
        pdfPreviewIframe.src = `/api/runs/${runId}/render/pdf?t=${Date.now()}`;
        pdfPreviewIframe.classList.remove("hidden");
      }
      if (pdfPlaceholder) pdfPlaceholder.classList.add("hidden");
    } else {
      if (renderStatusText) renderStatusText.textContent = `Rendering error: ${data.message || "Unknown error"}`;
    }
  } catch (err) {
    if (renderStatusText) renderStatusText.textContent = `Error: ${err.message}`;
    console.error(err);
  } finally {
    if (renderPdfBtn) renderPdfBtn.disabled = false;
  }
}

// Blog & Social Handlers
generateBlogBtn?.addEventListener("click", () => {
  generateBlogPosts(currentRunId);
});

async function generateBlogPosts(runId) {
  if (!runId) {
    alert("Please run a research topic first.");
    return;
  }
  if (generateBlogBtn) generateBlogBtn.disabled = true;
  if (blogStatusText) blogStatusText.textContent = "Generating blog copy...";
  try {
    const res = await fetch(`/api/runs/${runId}/export/blog`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        formats: ["blog", "newsletter", "twitter"]
      })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Blog generation failed.");
    }
    blogData = data.outputs || data;
    if (blogStatusText) blogStatusText.textContent = "Generated successfully!";
    displayActiveBlogTab();
  } catch (err) {
    if (blogStatusText) blogStatusText.textContent = `Error: ${err.message}`;
    console.error(err);
  } finally {
    if (generateBlogBtn) generateBlogBtn.disabled = false;
  }
}

function displayActiveBlogTab() {
  if (!blogData || !blogContentArea) return;
  
  if (blogSubTabBtn) blogSubTabBtn.classList.toggle("active", activeBlogSubTab === "blog");
  if (newsletterSubTabBtn) newsletterSubTabBtn.classList.toggle("active", activeBlogSubTab === "newsletter");
  if (twitterSubTabBtn) twitterSubTabBtn.classList.toggle("active", activeBlogSubTab === "twitter");
  
  let content = "No content available.";
  if (activeBlogSubTab === "blog") {
    content = blogData.blog || blogData.blog_markdown || "Blog post markdown not generated.";
  } else if (activeBlogSubTab === "newsletter") {
    content = blogData.newsletter || blogData.newsletter_summary || "Newsletter summary not generated.";
  } else if (activeBlogSubTab === "twitter") {
    const threads = blogData.twitter || blogData.twitter_thread || "Twitter thread not generated.";
    if (Array.isArray(threads)) {
      content = threads.map((tweet, idx) => `[Tweet ${idx + 1}]\n${tweet}`).join("\n\n");
    } else {
      content = threads;
    }
  }
  
  blogContentArea.textContent = content;
}

blogSubTabBtn?.addEventListener("click", () => {
  activeBlogSubTab = "blog";
  displayActiveBlogTab();
});

newsletterSubTabBtn?.addEventListener("click", () => {
  activeBlogSubTab = "newsletter";
  displayActiveBlogTab();
});

twitterSubTabBtn?.addEventListener("click", () => {
  activeBlogSubTab = "twitter";
  displayActiveBlogTab();
});

copyBlogContentBtn?.addEventListener("click", () => {
  if (!blogContentArea) return;
  const content = blogContentArea.textContent;
  if (!content || content.startsWith("No content generated")) return;
  navigator.clipboard.writeText(content).then(() => {
    const originalText = copyBlogContentBtn.textContent;
    copyBlogContentBtn.textContent = "Copied!";
    setTimeout(() => {
      copyBlogContentBtn.textContent = originalText;
    }, 2000);
  }).catch((err) => console.error("Clipboard copy failed:", err));
});


// ── Overleaf API Functions ──────────────────────────────────

async function checkOverleafStatus(runId) {
  const res = await fetch(`/api/runs/${runId}/overleaf/status`, {
    headers: { "Authorization": `Bearer ${authToken}` }
  });
  if (!res.ok) throw new Error("Failed to check Overleaf status");
  return res.json();
}

async function pushToOverleaf(runId, method, gitUrl, gitToken) {
  const body = { method };
  if (method === "git") {
    if (gitUrl) body.git_url = gitUrl;
    if (gitToken) body.git_token = gitToken;
  }
  const res = await fetch(`/api/runs/${runId}/overleaf/push`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authToken}`
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Push failed" }));
    throw new Error(err.detail || "Push failed");
  }
  return res.json();
}

async function pullFromOverleaf(runId, gitUrl, gitToken) {
  const body = { git_url: gitUrl };
  if (gitToken) body.git_token = gitToken;
  const res = await fetch(`/api/runs/${runId}/overleaf/pull`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authToken}`
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Pull failed" }));
    throw new Error(err.detail || "Pull failed");
  }
  return res.json();
}

// ── Overleaf Push Modal Logic ──────────────────────────────

function openOverleafPushModal() {
  if (!currentRunId) {
    appendMessage("assistant", "No research run to push. Start a research topic first.");
    return;
  }
  // Reset modal state
  overleafGitFields.classList.add("hidden");
  overleafPushStatus.classList.add("hidden");
  overleafPushResult.classList.add("hidden");
  overleafPushResult.innerHTML = "";
  overleafGitUrl.value = "";
  overleafGitToken.value = "";
  document.querySelector('input[name="overleafMethod"][value="snip"]').checked = true;
  overleafModalConfirm.disabled = false;
  overleafModalConfirm.textContent = "Push to Overleaf";
  overleafModal.classList.remove("hidden");
}

function closeOverleafPushModal() {
  overleafModal.classList.add("hidden");
}

// Toggle Git fields visibility
overleafMethodRadios.forEach((radio) => {
  radio.addEventListener("change", () => {
    const showGit = radio.value === "git";
    overleafGitFields.classList.toggle("hidden", !showGit);
    overleafModalConfirm.textContent = showGit ? "Push via Git" : "Push to Overleaf";
  });
});

overleafModalClose?.addEventListener("click", closeOverleafPushModal);
overleafModalCancel?.addEventListener("click", closeOverleafPushModal);

// Close modal on overlay click
overleafModal?.addEventListener("click", (e) => {
  if (e.target === overleafModal) closeOverleafPushModal();
});

overleafModalConfirm?.addEventListener("click", async () => {
  if (!currentRunId) return;
  const method = document.querySelector('input[name="overleafMethod"]:checked')?.value || "snip";
  const gitUrl = overleafGitUrl?.value.trim() || "";
  const gitToken = overleafGitToken?.value.trim() || "";

  // Validate git fields
  if (method === "git" && !gitUrl) {
    overleafGitUrl.style.borderColor = "#f43f5e";
    overleafGitUrl.focus();
    return;
  }
  overleafGitUrl.style.borderColor = "";

  // Show loading state
  overleafModalConfirm.disabled = true;
  overleafPushResult.classList.add("hidden");
  overleafPushResult.innerHTML = "";
  overleafPushStatus.classList.remove("hidden");
  overleafPushStatusText.textContent = method === "git" ? "Pushing via Git..." : "Generating Overleaf URL...";

  try {
    const result = await pushToOverleaf(currentRunId, method, gitUrl, gitToken);
    overleafPushStatus.classList.add("hidden");

    if (result.success) {
      if (method === "snip" && result.url) {
        // Snip URL: show with open button
        overleafPushResult.innerHTML = `
          <div class="modal-result-success">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <p>Overleaf project URL generated!</p>
            <a href="${result.url}" target="_blank" rel="noopener noreferrer" class="btn-link">Open in Overleaf</a>
          </div>
        `;
        // Also update the static link
        if (newOverleafLinkEl) {
          newOverleafLinkEl.href = result.url;
          newOverleafLinkEl.classList.remove("hidden");
          newOverleafLinkEl.textContent = "Open Overleaf Project";
        }
      } else if (method === "html" && result.html) {
        // HTML form: auto-submit via a temporary form
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = result.html;
        const form = tempDiv.querySelector("form");
        if (form) {
          document.body.appendChild(form);
          form.submit();
        }
        overleafPushResult.innerHTML = `
          <div class="modal-result-success">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <p>Opening Overleaf...</p>
            <p class="small muted">If nothing happens, check your popup blocker.</p>
          </div>
        `;
      } else if (method === "git" && result.success) {
        // Git push complete
        overleafPushResult.innerHTML = `
          <div class="modal-result-success">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <p>Successfully pushed to Overleaf via Git!</p>
            ${result.message ? `<p class="small muted">${result.message}</p>` : ''}
          </div>
        `;
        // Show the Overleaf link if returned
        if (result.overleaf_url && newOverleafLinkEl) {
          newOverleafLinkEl.href = result.overleaf_url;
          newOverleafLinkEl.classList.remove("hidden");
        }
      } else {
        overleafPushResult.innerHTML = `
          <div class="modal-result-success">
            <p>Push complete!</p>
            ${result.message ? `<p class="small muted">${result.message}</p>` : ''}
          </div>
        `;
      }
      appendMessage("assistant", `📤 Pushed to Overleaf (${method})`);
    } else {
      overleafPushResult.innerHTML = `
        <div class="modal-result-error">
          <p>Push failed: ${result.message || "Unknown error"}</p>
        </div>
      `;
    }
    overleafPushResult.classList.remove("hidden");
  } catch (err) {
    overleafPushStatus.classList.add("hidden");
    overleafPushResult.innerHTML = `
      <div class="modal-result-error">
        <p>Error: ${err.message}</p>
      </div>
    `;
    overleafPushResult.classList.remove("hidden");
  } finally {
    overleafModalConfirm.disabled = false;
    overleafModalConfirm.textContent = "Push to Overleaf";
  }
});

// ── Overleaf Pull Modal Logic ──────────────────────────────

function openOverleafPullModal() {
  if (!currentRunId) {
    appendMessage("assistant", "No research run to pull into. Start a research topic first.");
    return;
  }
  overleafPullStatus.classList.add("hidden");
  overleafPullResult.classList.add("hidden");
  overleafPullResult.innerHTML = "";
  overleafPullGitUrl.value = "";
  overleafPullGitToken.value = "";
  overleafPullModalConfirm.disabled = false;
  overleafPullModalConfirm.textContent = "Pull from Overleaf";
  overleafPullModal.classList.remove("hidden");
}

function closeOverleafPullModal() {
  overleafPullModal.classList.add("hidden");
}

overleafPullModalClose?.addEventListener("click", closeOverleafPullModal);
overleafPullModalCancel?.addEventListener("click", closeOverleafPullModal);

overleafPullModal?.addEventListener("click", (e) => {
  if (e.target === overleafPullModal) closeOverleafPullModal();
});

overleafPullModalConfirm?.addEventListener("click", async () => {
  if (!currentRunId) return;
  const gitUrl = overleafPullGitUrl?.value.trim();
  const gitToken = overleafPullGitToken?.value.trim() || "";

  if (!gitUrl) {
    overleafPullGitUrl.style.borderColor = "#f43f5e";
    overleafPullGitUrl.focus();
    return;
  }
  overleafPullGitUrl.style.borderColor = "";

  overleafPullModalConfirm.disabled = true;
  overleafPullResult.classList.add("hidden");
  overleafPullResult.innerHTML = "";
  overleafPullStatus.classList.remove("hidden");
  overleafPullStatusText.textContent = "Pulling from Overleaf...";

  try {
    const result = await pullFromOverleaf(currentRunId, gitUrl, gitToken);
    overleafPullStatus.classList.add("hidden");

    if (result.success) {
      // Update the editor with pulled content
      if (result.main_tex) {
        const codeEl = latexStreamEl?.querySelector("code");
        if (codeEl) {
          codeEl.textContent = result.main_tex;
          if (typeof Prism !== 'undefined') Prism.highlightElement(codeEl);
        }
      }
      overleafPullResult.innerHTML = `
        <div class="modal-result-success">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          <p>Successfully pulled from Overleaf!</p>
          ${result.message ? `<p class="small muted">${result.message}</p>` : ''}
        </div>
      `;
      appendMessage("assistant", "📥 Pulled latest changes from Overleaf");
    } else {
      overleafPullResult.innerHTML = `
        <div class="modal-result-error">
          <p>Pull failed: ${result.message || "Unknown error"}</p>
        </div>
      `;
    }
    overleafPullResult.classList.remove("hidden");
  } catch (err) {
    overleafPullStatus.classList.add("hidden");
    overleafPullResult.innerHTML = `
      <div class="modal-result-error">
        <p>Error: ${err.message}</p>
      </div>
    `;
    overleafPullResult.classList.remove("hidden");
  } finally {
    overleafPullModalConfirm.disabled = false;
    overleafPullModalConfirm.textContent = "Pull from Overleaf";
  }
});

// ── Overleaf Push/Pull Button Handlers ──────────────────────

overleafPushBtn?.addEventListener("click", async () => {
  if (!currentRunId) {
    appendMessage("assistant", "No research run to push. Start a research topic first.");
    return;
  }
  // Check status first to verify artifacts exist and show capabilities
  try {
    const status = await checkOverleafStatus(currentRunId);
    if (!status.artifacts_exist) {
      appendMessage("assistant", "No LaTeX artifacts found for this run. The research may still be in progress.");
      return;
    }
    // Pre-select the push method based on what's available
    if (!status.git_available) {
      // If git is not available, default to snip
      document.querySelector('input[name="overleafMethod"][value="snip"]').checked = true;
    }
  } catch (err) {
    // Status check failed — still allow the modal to open
    console.warn("Overleaf status check failed:", err);
  }
  openOverleafPushModal();
});

overleafPullBtn?.addEventListener("click", () => {
  if (!currentRunId) {
    appendMessage("assistant", "No research run to pull into. Start a research topic first.");
    return;
  }
  openOverleafPullModal();
});

(async () => {
  resetWorkbench();
  checkAuth();
})();
