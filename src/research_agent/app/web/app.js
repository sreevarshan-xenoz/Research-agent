const getMessagesEl = () => document.getElementById("messages");
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
const citationTabBtn = document.getElementById("citationTabBtn");
const datasetsTabBtn = document.getElementById("datasetsTabBtn");
const proposalTabBtn = document.getElementById("proposalTabBtn");
const trendsTabBtn = document.getElementById("trendsTabBtn");
const latexWorkbenchEl = document.getElementById("latexWorkbench");
const docWorkbenchEl = document.getElementById("docWorkbench");
const previewWorkbenchEl = document.getElementById("previewWorkbench");
const blogWorkbenchEl = document.getElementById("blogWorkbench");
const citationWorkbenchEl = document.getElementById("citationWorkbench");
const datasetsWorkbenchEl = document.getElementById("datasetsWorkbench");
const proposalWorkbenchEl = document.getElementById("proposalWorkbench");
const trendsWorkbenchEl = document.getElementById("trendsWorkbench");




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
const citationGraphStatus = document.getElementById("citationGraphStatus");
const citationNodeInfo = document.getElementById("citationNodeInfo");
const citationInfoTitle = document.getElementById("citationInfoTitle");
const citationInfoAuthors = document.getElementById("citationInfoAuthors");
const citationInfoYear = document.getElementById("citationInfoYear");
const citationInfoUrl = document.getElementById("citationInfoUrl");
const datasetsStatusText = document.getElementById("datasetsStatusText");
const datasetsContainer = document.getElementById("datasetsContainer");
const proposalPIName = document.getElementById("proposalPIName");
const proposalPIInstitution = document.getElementById("proposalPIInstitution");
const proposalAgency = document.getElementById("proposalAgency");
const proposalTitle = document.getElementById("proposalTitle");
const proposalAbstract = document.getElementById("proposalAbstract");
const generateProposalBtn = document.getElementById("generateProposalBtn");
const proposalContentContainer = document.getElementById("proposalContentContainer");
const proposalContentArea = document.getElementById("proposalContentArea");
const copyProposalBtn = document.getElementById("copyProposalBtn");
const proposalStatusText = document.getElementById("proposalStatusText");
const proposalFormBlock = document.getElementById("proposalFormBlock");
const trendsQueryInput = document.getElementById("trendsQueryInput");
const searchTrendsBtn = document.getElementById("searchTrendsBtn");
const trendsDashboardArea = document.getElementById("trendsDashboardArea");
const trendsStatusText = document.getElementById("trendsStatusText");
const trendsTimelineContainer = document.getElementById("trendsTimelineContainer");
const trendsKeywordsContainer = document.getElementById("trendsKeywordsContainer");
const trendsAuthorsContainer = document.getElementById("trendsAuthorsContainer");
const trendsVenuesContainer = document.getElementById("trendsVenuesContainer");
const trendsEmailInput = document.getElementById("trendsEmailInput");
const subscribeTrendsBtn = document.getElementById("subscribeTrendsBtn");

// Reproducibility Dashboard Elements (P29)
const reproducibilityStatusText = document.getElementById("reproducibilityStatusText");
const reproOverallScore = document.getElementById("reproOverallScore");
const reproPassed = document.getElementById("reproPassed");
const reproFailed = document.getElementById("reproFailed");
const reproPartial = document.getElementById("reproPartial");
const reproUnverifiable = document.getElementById("reproUnverifiable");
const reproVerdict = document.getElementById("reproVerdict");
const reproClaimsContainer = document.getElementById("reproClaimsContainer");
const reproEmptyState = document.getElementById("reproEmptyState");
const reproViewReportBtn = document.getElementById("reproViewReportBtn");
const reproViewScriptsBtn = document.getElementById("reproViewScriptsBtn");
const reproReportModal = document.getElementById("reproReportModal");
const reproReportContent = document.getElementById("reproReportContent");
const reproReportModalClose = document.getElementById("reproReportModalClose");
const reproReportModalCloseBtn = document.getElementById("reproReportModalCloseBtn");
const reproCopyReportBtn = document.getElementById("reproCopyReportBtn");
const reproScriptsModal = document.getElementById("reproScriptsModal");
const reproScriptsContent = document.getElementById("reproScriptsContent");
const reproScriptsModalClose = document.getElementById("reproScriptsModalClose");
const reproScriptsModalCloseBtn = document.getElementById("reproScriptsModalCloseBtn");








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

// Register QuillCursors module before Quill creation (for cursor presence)
if (typeof Quill !== "undefined" && typeof QuillCursors !== "undefined") {
  try {
    Quill.register("modules/cursors", QuillCursors);
  } catch (e) {
    console.warn("Failed to register QuillCursors:", e);
  }
}
// Initialize Quill Editor (if element exists)
let quill = null;
try {
  if (docEditorEl) {
    quill = new Quill("#docEditor", {
      theme: "snow",
      modules: {
        cursors: true,
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
} catch (err) {
  console.error("Failed to initialize Quill editor:", err);
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
      const response = await fetch("/api/auth/jwt/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password: password }),
      });
      if (!response.ok) throw new Error("Invalid credentials");
      const data = await response.json();
      authToken = data.access_token;
    } else {
      const response = await fetch("/api/auth/register", {
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
    if (authStatusEl) authStatusEl.textContent = err.message;
  }
});

function checkAuth() {
  if (authToken) {
    authOverlayEl.classList.add("hidden");
    appShellEl.classList.remove("hidden");
    tryResumeSession();
    loadResearchSuggestions();
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
  if (citationTabBtn) citationTabBtn.classList.toggle("active", tab === "citation");
  if (datasetsTabBtn) datasetsTabBtn.classList.toggle("active", tab === "datasets");
  if (proposalTabBtn) proposalTabBtn.classList.toggle("active", tab === "proposal");
  if (trendsTabBtn) trendsTabBtn.classList.toggle("active", tab === "trends");
  if (reproducibilityTabBtn) reproducibilityTabBtn.classList.toggle("active", tab === "reproducibility");
  if (submissionTabBtn) submissionTabBtn.classList.toggle("active", tab === "submission");
  if (libraryTabBtn) libraryTabBtn.classList.toggle("active", tab === "library");
  if (paperGitTabBtn) paperGitTabBtn.classList.toggle("active", tab === "paperGit");
  if (pluginsTabBtn) pluginsTabBtn.classList.toggle("active", tab === "plugins");

  const docPanel = document.querySelector(".doc-panel");
  const latexPanel = document.querySelector(".latex-panel");
  const previewPanel = document.querySelector(".preview-panel");
  const blogPanel = document.querySelector(".blog-panel");
  const citationPanel = document.querySelector(".citation-panel");
  const datasetsPanel = document.querySelector(".datasets-panel");
  const proposalPanel = document.querySelector(".proposal-panel");
  const trendsPanel = document.querySelector(".trends-panel");
  const reproducibilityPanel = document.querySelector(".reproducibility-panel");
  const submissionPanel = document.querySelector(".submission-panel");
  const kgPanel = document.querySelector(".kg-panel");

  if (docPanel) docPanel.classList.toggle("active", tab === "doc");
  if (latexPanel) latexPanel.classList.toggle("active", tab === "latex");
  if (previewPanel) previewPanel.classList.toggle("active", tab === "preview");
  if (blogPanel) blogPanel.classList.toggle("active", tab === "blog");
  if (citationPanel) citationPanel.classList.toggle("active", tab === "citation");
  if (datasetsPanel) datasetsPanel.classList.toggle("active", tab === "datasets");
  if (proposalPanel) proposalPanel.classList.toggle("active", tab === "proposal");
  if (trendsPanel) trendsPanel.classList.toggle("active", tab === "trends");
  if (reproducibilityPanel) reproducibilityPanel.classList.toggle("active", tab === "reproducibility");
  if (submissionPanel) submissionPanel.classList.toggle("active", tab === "submission");
  if (kgPanel) kgPanel.classList.toggle("active", tab === "kg");
  const libraryPanel = document.querySelector(".library-panel");
  if (libraryPanel) libraryPanel.classList.toggle("active", tab === "library");
  const pgPanel = document.querySelector(".paper-git-panel");
  if (pgPanel) pgPanel.classList.toggle("active", tab === "paperGit");
  const pluginsPanel = document.querySelector(".plugins-panel");
  if (pluginsPanel) pluginsPanel.classList.toggle("active", tab === "plugins");

  if (tab === "citation") {
    loadCitationGraph();
  } else if (tab === "datasets") {
    loadDiscoveredDatasets();
  } else if (tab === "proposal") {
    loadProposalTab();
  } else if (tab === "trends") {
    loadTrendsTab();
  } else if (tab === "reproducibility") {
    loadReproducibilityData();
  } else if (tab === "kg") {
    loadKgExplorer();
  } else if (tab === "submission") {
    loadSubmissionPipeline();
  } else if (tab === "library") {
    if (typeof loadLibraryBrowser === "function") loadLibraryBrowser();
  } else if (tab === "paperGit") {
    loadPaperGitBrowser();
  } else if (tab === "plugins") {
    if (typeof loadPluginsBrowser === "function") loadPluginsBrowser();
  }
}

function loadKgExplorer() {
  if (!kgTabBtn) return;
  if (kgStatusText) kgStatusText.textContent = "Loading knowledge graph...";
  if (kgExplorerIframe) {
    // Refresh the iframe to ensure latest data
    kgExplorerIframe.src = "/api/knowledge-graph/explorer?t=" + Date.now();
  }
  // Fetch metadata
  fetch("/api/knowledge-graph/data", {
    headers: { "Authorization": `Bearer ${authToken}` }
  })
    .then(res => res.json())
    .then(data => {
      const nodeCount = data.nodes ? data.nodes.length : 0;
      const edgeCount = data.edges ? data.edges.length : 0;
      if (kgStatusText) kgStatusText.textContent = `${nodeCount} entities, ${edgeCount} relations`;
      if (kgMeta) kgMeta.textContent = `Cross-run knowledge graph`;
    })
    .catch(err => {
      if (kgStatusText) kgStatusText.textContent = "No knowledge graph data yet";
    });
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

  // Reset Citation Graph elements
  if (citationGraphStatus) citationGraphStatus.textContent = "No active run loaded";
  if (citationNodeInfo) citationNodeInfo.classList.add("hidden");
  if (typeof d3 !== "undefined") d3.select("#citationGraphSvg").selectAll("*").remove();

  // Reset Datasets elements
  if (datasetsStatusText) datasetsStatusText.textContent = "No active run loaded";
  if (datasetsContainer) datasetsContainer.innerHTML = "";

  // Reset Proposal elements
  if (proposalStatusText) proposalStatusText.textContent = "No active run loaded";
  if (proposalFormBlock) proposalFormBlock.classList.add("hidden");
  if (proposalContentContainer) proposalContentContainer.classList.add("hidden");
  if (proposalContentArea) proposalContentArea.textContent = "";
  if (proposalTitle) proposalTitle.value = "";
  if (proposalAbstract) proposalAbstract.value = "";

  // Reset Reproducibility elements
  if (reproducibilityStatusText) reproducibilityStatusText.textContent = "No active run loaded";
  if (reproOverallScore) reproOverallScore.textContent = "—";
  if (reproPassed) reproPassed.textContent = "—";
  if (reproFailed) reproFailed.textContent = "—";
  if (reproPartial) reproPartial.textContent = "—";
  if (reproUnverifiable) reproUnverifiable.textContent = "—";
  if (reproVerdict) reproVerdict.style.display = "none";
  if (reproClaimsContainer) reproClaimsContainer.innerHTML = "<p class='small muted'>Load a research run to see reproducibility results.</p>";

  // Reset Trends elements
  if (trendsStatusText) trendsStatusText.textContent = "Enter a query to view trend analytics";
  if (trendsDashboardArea) trendsDashboardArea.classList.add("hidden");
  if (trendsTimelineContainer) trendsTimelineContainer.innerHTML = "";
  if (trendsKeywordsContainer) trendsKeywordsContainer.innerHTML = "";
  if (trendsAuthorsContainer) trendsAuthorsContainer.innerHTML = "";
  if (trendsVenuesContainer) trendsVenuesContainer.innerHTML = "";
  if (trendsQueryInput) trendsQueryInput.value = "";

  // P26: Reset hypothesis and strategy panels
  const hypPanel = document.getElementById("hypothesisPanel");
  if (hypPanel) hypPanel.innerHTML = '<p class="small muted">Run a research topic to generate hypotheses.</p>';
  const hypBadge = document.getElementById("hypothesisBadge");
  if (hypBadge) hypBadge.textContent = "0";
  const stratPanel = document.getElementById("strategyPanel");
  if (stratPanel) stratPanel.innerHTML = '<p class="small muted">Run a research topic to generate strategy recommendations.</p>';
  const stratBadge = document.getElementById("strategyBadge");
  if (stratBadge) stratBadge.textContent = "—";
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
  const messagesEl = getMessagesEl();
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

function normalizeStatus(raw) {
  if (!raw) return "pending";
  const s = String(raw).toLowerCase().trim();
  if (["done", "complete", "completed", "success", "finished"].includes(s)) return "complete";
  if (["running", "active", "in_progress", "working"].includes(s)) return "running";
  if (["waiting", "blocked", "paused"].includes(s)) return "waiting";
  if (["error", "failed"].includes(s)) return "error";
  return "pending";
}

function appendDiscovery(name, detail) {
  if (!discoveryFeedEl) return;
  // Remove the placeholder text if present
  const placeholder = discoveryFeedEl.querySelector(".muted");
  if (placeholder) placeholder.remove();

  const item = document.createElement("div");
  item.className = "discovery-item fade-in";
  const source = document.createElement("span");
  source.className = "source";
  source.textContent = name;
  item.appendChild(source);
  if (detail) {
    const detailEl = document.createElement("div");
    detailEl.className = "small";
    detailEl.textContent = detail;
    item.appendChild(detailEl);
  }
  discoveryFeedEl.appendChild(item);
  discoveryFeedEl.scrollTop = discoveryFeedEl.scrollHeight;
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
}
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
        // P26: Render hypothesis and strategy panels
        if (payload.generated_hypotheses) renderHypotheses(payload.generated_hypotheses);
        if (payload.research_strategy) renderStrategy(payload.research_strategy);
        if (payload.gap_exploration) renderGapExploration(payload.gap_exploration);
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


// P26: Auto-Discover button — launches autonomous research on a trending topic
const autoDiscoverBtn = document.getElementById("autoDiscoverBtn");
autoDiscoverBtn?.addEventListener("click", async () => {
  // Set autonomy mode to autonomous and send empty topic signal
  // Ensure paper research mode for the autonomous pipeline
  const paperRadio = document.querySelector('input[name="runMode"][value="paper"]');
  if (paperRadio) paperRadio.click();
  if (autonomySelect) autonomySelect.value = "autonomous";
  if (messageInput) messageInput.value = "auto-discover";
  chatForm?.dispatchEvent(new Event("submit"));
});

newSessionBtn?.addEventListener("click", () => {
  sessionId = null; localStorage.removeItem("research_session_id");
  resetWorkbench(); appendMessage("assistant", "Session reset.");
  loadResearchSuggestions();
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
citationTabBtn?.addEventListener("click", () => switchWorkbenchTab("citation"));
datasetsTabBtn?.addEventListener("click", () => switchWorkbenchTab("datasets"));
proposalTabBtn?.addEventListener("click", () => switchWorkbenchTab("proposal"));
trendsTabBtn?.addEventListener("click", () => switchWorkbenchTab("trends"));
const kgTabBtn = document.getElementById("kgTabBtn");
const submissionTabBtn = document.getElementById("submissionTabBtn");
const libraryTabBtn = document.getElementById("libraryTabBtn");
const paperGitTabBtn = document.getElementById("paperGitTabBtn");
const pluginsTabBtn = document.getElementById("pluginsTabBtn");

reproducibilityTabBtn?.addEventListener("click", () => switchWorkbenchTab("reproducibility"));
kgTabBtn?.addEventListener("click", () => switchWorkbenchTab("kg"));
submissionTabBtn?.addEventListener("click", () => switchWorkbenchTab("submission"));
libraryTabBtn?.addEventListener("click", () => switchWorkbenchTab("library"));
  paperGitTabBtn?.addEventListener("click", () => switchWorkbenchTab("paperGit"));
pluginsTabBtn?.addEventListener("click", () => switchWorkbenchTab("plugins"));
copyDocBtn?.addEventListener("click", copyDocumentToClipboard);





// Preview PDF Handlers
renderPdfBtn?.addEventListener("click", () => {
  compilePdfForRun(currentRunId);
});

async function compilePdfForRun(runId) {
  if (!runId) {
    if (renderStatusText) renderStatusText.textContent = "Please run a research topic first.";
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
    if (blogStatusText) blogStatusText.textContent = "Please run a research topic first.";
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

async function loadCitationGraph() {
  if (!currentRunId) {
    if (citationGraphStatus) citationGraphStatus.textContent = "No active run loaded yet.";
    return;
  }
  if (citationGraphStatus) citationGraphStatus.textContent = "Loading citation network...";
  try {
    const res = await fetch(`/api/runs/${currentRunId}/citation-graph`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) {
      throw new Error("No citation data found.");
    }
    const data = await res.json();
    if (citationGraphStatus) citationGraphStatus.textContent = `Citation Network: ${data.nodes.length} papers, ${data.edges.length} connections`;
    drawCitationGraph(data);
  } catch (err) {
    if (citationGraphStatus) citationGraphStatus.textContent = `Failed to load graph: ${err.message}`;
    if (typeof d3 !== "undefined") d3.select("#citationGraphSvg").selectAll("*").remove();
  }
}

function drawCitationGraph(data) {
  if (typeof d3 === "undefined") {
    console.error("D3 library is not loaded.");
    return;
  }

  const svg = d3.select("#citationGraphSvg");
  svg.selectAll("*").remove();

  if (!data || !data.nodes || data.nodes.length === 0) {
    if (citationGraphStatus) citationGraphStatus.textContent = "No citation graph data available for this run.";
    return;
  }

  const width = svg.node().clientWidth || 600;
  const height = svg.node().clientHeight || 400;

  const g = svg.append("g");

  const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on("zoom", (event) => {
      g.attr("transform", event.transform);
    });

  svg.call(zoom);

  const simulation = d3.forceSimulation(data.nodes)
    .force("link", d3.forceLink(data.edges).id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-150))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(25));

  const link = g.append("g")
    .attr("stroke", "rgba(255, 255, 255, 0.15)")
    .attr("stroke-width", 1.5)
    .selectAll("line")
    .data(data.edges)
    .join("line");

  const node = g.append("g")
    .selectAll("circle")
    .data(data.nodes)
    .join("circle")
    .attr("r", d => d.group === 1 ? 8 : 6)
    .attr("fill", d => d.group === 1 ? "var(--primary, #00d2ff)" : "#ff007f")
    .attr("stroke", "rgba(255, 255, 255, 0.4)")
    .attr("stroke-width", 1.5)
    .style("cursor", "pointer")
    .call(d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended));

  node.on("click", (event, d) => {
    if (citationNodeInfo) citationNodeInfo.classList.remove("hidden");
    if (citationInfoTitle) citationInfoTitle.textContent = d.label || "Untitled Paper";
    if (citationInfoAuthors) citationInfoAuthors.textContent = d.authors ? `Authors: ${d.authors}` : "Authors: N/A";
    if (citationInfoYear) citationInfoYear.textContent = d.year ? `Year: ${d.year}` : "";
    if (citationInfoUrl) {
      if (d.url) {
        citationInfoUrl.href = d.url;
        citationInfoUrl.style.display = "inline";
      } else {
        citationInfoUrl.style.display = "none";
      }
    }
  });

  node.append("title")
    .text(d => d.label);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);
  });

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
}

async function loadDiscoveredDatasets() {
  if (!currentRunId) {
    if (datasetsStatusText) datasetsStatusText.textContent = "No active run loaded yet.";
    return;
  }
  if (datasetsStatusText) datasetsStatusText.textContent = "Searching relevant datasets...";
  try {
    const res = await fetch(`/api/runs/${currentRunId}/datasets`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) {
      throw new Error("Failed to fetch datasets.");
    }
    const data = await res.json();
    const list = data.datasets || [];
    if (datasetsStatusText) datasetsStatusText.textContent = `Discovered ${list.length} related datasets`;
    renderDiscoveredDatasets(list);
  } catch (err) {
    if (datasetsStatusText) datasetsStatusText.textContent = `Failed to load datasets: ${err.message}`;
    if (datasetsContainer) datasetsContainer.innerHTML = `<p class="muted">Error: ${err.message}</p>`;
  }
}

function renderDiscoveredDatasets(datasets) {
  if (!datasetsContainer) return;
  if (!datasets || datasets.length === 0) {
    datasetsContainer.innerHTML = '<p class="muted">No datasets found matching this topic.</p>';
    return;
  }

  datasetsContainer.innerHTML = datasets.map(ds => {
    const providerBadge = ds.provider === "huggingface" 
      ? '<span class="badge" style="background: #ffbd2e; color: #000;">Hugging Face</span>'
      : '<span class="badge" style="background: #20beff; color: #000;">Kaggle</span>';
      
    const desc = ds.description ? ds.description : "No description provided.";
    const likesText = ds.likes !== undefined && ds.likes !== null ? ` • Likes: ${ds.likes}` : "";
    const downloadsText = ds.downloads ? ` • Downloads: ${ds.downloads.toLocaleString()}` : "";

    return `
      <div class="dataset-card">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;">
          <h4 style="margin: 0; color: #fff; font-size: 0.95rem; font-weight: 600;">${ds.name}</h4>
          ${providerBadge}
        </div>
        <p style="margin: 0; font-size: 0.8rem; opacity: 0.7; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;" title="${desc}">${desc}</p>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; opacity: 0.5; margin-top: 4px;">
          <span>${downloadsText}${likesText}</span>
          <a href="${ds.url}" target="_blank" style="color: var(--primary); text-decoration: underline;">Open Dataset</a>
        </div>
      </div>
    `;
  }).join("");
}

function loadProposalTab() {
  if (!currentRunId) {
    if (proposalStatusText) proposalStatusText.textContent = "No active run loaded yet.";
    if (proposalFormBlock) proposalFormBlock.classList.add("hidden");
    if (proposalContentContainer) proposalContentContainer.classList.add("hidden");
    return;
  }
  
  if (proposalStatusText) proposalStatusText.textContent = "Ready to generate proposal";
  if (proposalFormBlock) proposalFormBlock.classList.remove("hidden");
  
  if (proposalTitle && !proposalTitle.value) {
    const text = messageInput?.value.trim();
    proposalTitle.value = text || "Research Project Proposal";
  }
  if (proposalAbstract && !proposalAbstract.value) {
    if (quill) {
      const docText = quill.getText().trim();
      if (docText && !docText.startsWith("Research document")) {
        proposalAbstract.value = docText.split("\n").slice(0, 8).join("\n");
      }
    }
  }
}

generateProposalBtn?.addEventListener("click", async () => {
  if (!currentRunId) return;
  
  const title = proposalTitle?.value.trim();
  const piName = proposalPIName?.value.trim() || "Dr. Alex Researcher";
  const piInstitution = proposalPIInstitution?.value.trim() || "Stanford University";
  const abstract = proposalAbstract?.value.trim() || "";
  const agency = proposalAgency?.value || "nsf";
  
  if (!title) {
    if (proposalStatusText) proposalStatusText.textContent = "Please provide a Project Title.";
    return;
  }
  
  if (proposalStatusText) proposalStatusText.textContent = "Generating grant proposal...";
  generateProposalBtn.disabled = true;
  generateProposalBtn.textContent = "Generating...";
  
  try {
    const res = await fetch(`/api/runs/${currentRunId}/export/grant`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        title,
        pi_name: piName,
        pi_institution: piInstitution,
        abstract,
        agency
      })
    });
    
    if (!res.ok) {
      throw new Error("Failed to generate proposal.");
    }
    const data = await res.json();
    
    if (proposalStatusText) proposalStatusText.textContent = `Proposal generated for ${agency.toUpperCase()}`;
    if (proposalContentContainer) proposalContentContainer.classList.remove("hidden");
    if (proposalContentArea) {
      proposalContentArea.textContent = data.grant_proposal || "No content returned.";
    }
  } catch (err) {
    if (proposalStatusText) proposalStatusText.textContent = `Generation failed: ${err.message}`;
  } finally {
    generateProposalBtn.disabled = false;
    generateProposalBtn.textContent = "Generate Proposal";
  }
});

copyProposalBtn?.addEventListener("click", () => {
  const content = proposalContentArea?.textContent;
  if (!content) return;
  navigator.clipboard.writeText(content).then(() => {
    const origText = copyProposalBtn.textContent;
    copyProposalBtn.textContent = "Copied!";
    setTimeout(() => { copyProposalBtn.textContent = origText; }, 2000);
  }).catch(err => {
    console.error("Clipboard copy failed:", err);
  });
});

function loadTrendsTab() {
  if (trendsQueryInput && !trendsQueryInput.value && currentRunId) {
    const topic = messageInput?.value?.trim();
    if (topic) trendsQueryInput.value = topic;
  }
}

function renderTrendBar(container, items, maxCount, colorVar = "var(--primary-glow)") {
  if (!container) return;
  if (!items || items.length === 0) {
    container.innerHTML = '<p style="opacity: 0.5; font-size: 0.8rem; margin: 0;">No data available</p>';
    return;
  }
  container.innerHTML = items.map(item => {
    const pct = maxCount > 0 ? Math.round((item.count / maxCount) * 100) : 0;
    const label = item.name || item.year || "Unknown";
    return `
      <div class="trend-bar-row">
        <span class="trend-bar-label" title="${label}">${label}</span>
        <div class="trend-bar-track">
          <div class="trend-bar-fill" style="width: ${pct}%; background: ${colorVar};"></div>
        </div>
        <span style="font-size: 0.75rem; opacity: 0.6; min-width: 28px; text-align: right;">${item.count}</span>
      </div>
    `;
  }).join("");
}

async function searchTrends() {
  const query = trendsQueryInput?.value?.trim();
  if (!query) {
    if (trendsStatusText) trendsStatusText.textContent = "Please enter a search query.";
    return;
  }

  if (trendsStatusText) trendsStatusText.textContent = `Analyzing trends for: "${query}"...`;
  if (searchTrendsBtn) { searchTrendsBtn.disabled = true; searchTrendsBtn.textContent = "Analyzing..."; }

  try {
    const res = await fetch(`/api/trends?query=${encodeURIComponent(query)}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Failed to fetch trends data.");
    const data = await res.json();

    if (trendsStatusText) trendsStatusText.textContent = `Found ${data.total_papers || 0} papers for "${data.query}"`;
    if (trendsDashboardArea) trendsDashboardArea.classList.remove("hidden");

    const timelineMax = data.timeline?.length ? Math.max(...data.timeline.map(t => t.count)) : 1;
    renderTrendBar(trendsTimelineContainer, data.timeline?.slice(-12) || [], timelineMax, "var(--primary-glow)");

    const keywordMax = data.top_keywords?.length ? Math.max(...data.top_keywords.map(k => k.count)) : 1;
    renderTrendBar(trendsKeywordsContainer, data.top_keywords || [], keywordMax, "#a78bfa");

    const authorMax = data.top_authors?.length ? Math.max(...data.top_authors.map(a => a.count)) : 1;
    renderTrendBar(trendsAuthorsContainer, data.top_authors?.slice(0, 8) || [], authorMax, "#38bdf8");

    const venueMax = data.top_venues?.length ? Math.max(...data.top_venues.map(v => v.count)) : 1;
    renderTrendBar(trendsVenuesContainer, data.top_venues?.slice(0, 8) || [], venueMax, "#34d399");

  } catch (err) {
    if (trendsStatusText) trendsStatusText.textContent = `Error: ${err.message}`;
  } finally {
    if (searchTrendsBtn) { searchTrendsBtn.disabled = false; searchTrendsBtn.textContent = "Analyze Trends"; }
  }
}

searchTrendsBtn?.addEventListener("click", searchTrends);

trendsQueryInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchTrends();
});

subscribeTrendsBtn?.addEventListener("click", async () => {
  const email = trendsEmailInput?.value?.trim();
  const query = trendsQueryInput?.value?.trim();
  if (!email) { if (trendsStatusText) trendsStatusText.textContent = "Please enter your email address."; return; }
  if (!query) { if (trendsStatusText) trendsStatusText.textContent = "Please enter a search query first."; return; }

  try {
    const res = await fetch(`/api/trends/report?query=${encodeURIComponent(query)}&email=${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    const data = await res.json();
    if (data.success) {
      subscribeTrendsBtn.textContent = "Subscribed ✓";
      subscribeTrendsBtn.disabled = true;
      setTimeout(() => { subscribeTrendsBtn.textContent = "Subscribe"; subscribeTrendsBtn.disabled = false; }, 3000);
    }
  } catch (err) {
    if (trendsStatusText) trendsStatusText.textContent = "Failed to subscribe: " + err.message;
  }
});

// ── Reproducibility Dashboard Functions (P29) ───────────────────────────────

let _reproDataCache = null;

async function loadReproducibilityData() {
  if (!currentRunId) {
    if (reproducibilityStatusText) reproducibilityStatusText.textContent = "No active run loaded yet.";
    if (reproClaimsContainer) reproClaimsContainer.innerHTML = "<p class='small muted'>Load a research run to see reproducibility results.</p>";
    return;
  }

  if (reproducibilityStatusText) reproducibilityStatusText.textContent = "Loading reproducibility data...";

  try {
    const res = await fetch(`/api/runs/${currentRunId}/reproducibility`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Failed to fetch reproducibility data");

    const data = await res.json();
    _reproDataCache = data;

    if (!data.has_reproducibility || data.total_claims === 0) {
      if (reproducibilityStatusText) reproducibilityStatusText.textContent = data.message || "No reproducibility data available.";
      if (reproOverallScore) reproOverallScore.textContent = "\u2014";
      if (reproPassed) reproPassed.textContent = "0";
      if (reproFailed) reproFailed.textContent = "0";
      if (reproPartial) reproPartial.textContent = "0";
      if (reproUnverifiable) reproUnverifiable.textContent = "0";
      if (reproClaimsContainer) reproClaimsContainer.innerHTML = "<p class='small muted'>" + (data.message || "No reproducibility data found.") + "</p>";
      if (reproVerdict) reproVerdict.style.display = "none";
      return;
    }

    if (reproducibilityStatusText) reproducibilityStatusText.textContent = data.total_claims + " claims analyzed";
    renderReproducibilityDashboard(data);
  } catch (err) {
    if (reproducibilityStatusText) reproducibilityStatusText.textContent = "Failed to load: " + err.message;
    if (reproClaimsContainer) reproClaimsContainer.innerHTML = "<p class='small muted'>Error: " + err.message + "</p>";
  }
}

function renderReproducibilityDashboard(data) {
  const summary = data.summary || {};
  const passed = summary.passed || 0;
  const failed = summary.failed || 0;
  const partial = summary.partial || 0;
  const unverifiable = summary.unverifiable || 0;
  const overallScore = data.overall_score || 0;
  const items = data.items || [];

  // Update score cards
  if (reproOverallScore) reproOverallScore.textContent = (overallScore * 100).toFixed(0) + "%";
  if (reproPassed) reproPassed.textContent = passed;
  if (reproFailed) reproFailed.textContent = failed;
  if (reproPartial) reproPartial.textContent = partial;
  if (reproUnverifiable) reproUnverifiable.textContent = unverifiable;

  // Update verdict banner
  if (reproVerdict) {
    let verdictText = "";
    let verdictBg = "";
    let verdictColor = "";
    if (overallScore >= 0.8) {
      verdictText = "\u2705 Strong Reproducibility \u2014 " + (overallScore * 100).toFixed(0) + "% of claims verified";
      verdictBg = "rgba(16, 185, 129, 0.1)";
      verdictColor = "#34d399";
    } else if (overallScore >= 0.5) {
      verdictText = "\U0001f7e1 Partial Reproducibility \u2014 " + (overallScore * 100).toFixed(0) + "% of claims verified";
      verdictBg = "rgba(245, 158, 11, 0.1)";
      verdictColor = "#f59e0b";
    } else {
      verdictText = "\u274c Poor Reproducibility \u2014 Only " + (overallScore * 100).toFixed(0) + "% of claims verified";
      verdictBg = "rgba(244, 63, 94, 0.1)";
      verdictColor = "#f43f5e";
    }
    reproVerdict.textContent = verdictText;
    reproVerdict.style.display = "block";
    reproVerdict.style.background = verdictBg;
    reproVerdict.style.color = verdictColor;
    reproVerdict.style.border = "1px solid " + verdictColor + "33";
  }

  // Render per-claim results
  if (reproClaimsContainer) {
    if (items.length === 0) {
      reproClaimsContainer.innerHTML = "<p class='small muted'>No claim results available.</p>";
      return;
    }

    reproClaimsContainer.innerHTML = items.map((item, idx) => {
      const status = item.status || "unknown";
      const statusEmoji = status === "pass" ? "\u2705" : status === "fail" ? "\u274c" : status === "partial" ? "\U0001f7e1" : "\u2b1c";
      const statusColor = status === "pass" ? "#34d399" : status === "fail" ? "#f43f5e" : status === "partial" ? "#f59e0b" : "#71717a";
      const claimText = item.claim_text || "Unknown claim";
      const claimedVal = item.claimed_value || "\u2014";
      const actualVal = item.actual_value || "\u2014";
      const confidence = item.confidence || 0;
      const duration = item.duration_seconds || 0;

      return `
        <div class="repro-claim-card" style="background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: var(--radius-md); padding: 12px; transition: all 0.2s ease;">
          <div style="display: flex; align-items: flex-start; gap: 10px;">
            <span style="font-size: 1.1rem; line-height: 1.4;">${statusEmoji}</span>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 0.8rem; color: #e4e4e7; line-height: 1.4; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;" title="${claimText.replace(/"/g, "&quot;")}">${claimText}</div>
              <div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.7rem; color: #71717a;">
                <span>Claimed: <strong style="color: #a1a1aa;">${String(claimedVal).substring(0, 60)}</strong></span>
                <span>Actual: <strong style="color: ${statusColor};">${String(actualVal).substring(0, 60)}</strong></span>
                <span>Confidence: <strong>${(confidence * 100).toFixed(0)}%</strong></span>
                <span>Runtime: <strong>${duration.toFixed(1)}s</strong></span>
              </div>
              <div style="margin-top: 6px;">
                <span class="status-pill" style="display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px; font-size: 0.6rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; background: ${statusColor}22; color: ${statusColor};">${statusEmoji} ${status}</span>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }
}

// ── Reproducibility Modal Handlers ───────────────────────────────

function openReproReportModal() {
  if (!currentRunId) return;
  if (reproReportContent) reproReportContent.textContent = "Loading report...";
  if (reproReportModal) reproReportModal.classList.remove("hidden");

  fetch(`/api/runs/${currentRunId}/reproducibility/report`, {
    headers: { "Authorization": `Bearer ${authToken}` }
  })
    .then(res => {
      if (!res.ok) throw new Error("Report not found");
      return res.json();
    })
    .then(data => {
      if (reproReportContent) reproReportContent.textContent = data.report || "No report content.";
    })
    .catch(err => {
      if (reproReportContent) reproReportContent.textContent = "Error: " + err.message;
    });
}

function closeReproReportModal() {
  if (reproReportModal) reproReportModal.classList.add("hidden");
}

function openReproScriptsModal() {
  if (!currentRunId) return;
  if (reproScriptsContent) reproScriptsContent.innerHTML = "<p class='muted' style='font-size: 0.85rem;'>Loading scripts...</p>";
  if (reproScriptsModal) reproScriptsModal.classList.remove("hidden");

  fetch(`/api/runs/${currentRunId}/reproducibility/scripts`, {
    headers: { "Authorization": `Bearer ${authToken}` }
  })
    .then(res => {
      if (!res.ok) throw new Error("Scripts not found");
      return res.json();
    })
    .then(data => {
      const scripts = data.scripts || [];
      if (scripts.length === 0) {
        if (reproScriptsContent) reproScriptsContent.innerHTML = "<p class='muted' style='font-size: 0.85rem;'>No verification scripts found.</p>";
        return;
      }
      let html = "<div style='display: flex; flex-direction: column; gap: 8px;'>";
      scripts.forEach(s => {
        html += `
          <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); padding: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-weight: 600; font-size: 0.8rem; color: #e4e4e7;">${s.name}</span>
              <span style="font-size: 0.65rem; color: #71717a;">${s.size_bytes} bytes</span>
            </div>
            <pre style="background: #050505; padding: 8px; border-radius: 4px; font-size: 0.7rem; line-height: 1.4; max-height: 200px; overflow-y: auto; margin: 0;" class="mono"><code>${s.code.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>
          </div>
        `;
      });
      html += "</div>";
      if (reproScriptsContent) reproScriptsContent.innerHTML = html;
    })
    .catch(err => {
      if (reproScriptsContent) reproScriptsContent.innerHTML = "<p class='muted' style='font-size: 0.85rem;'>Error: " + err.message + "</p>";
    });
}

function closeReproScriptsModal() {
  if (reproScriptsModal) reproScriptsModal.classList.add("hidden");
}
// ── Model Settings Panel (P12) ──────────────────────────────────────────────────

const settingsPanelHeader = document.getElementById("settingsPanelHeader");
const settingsPanelBody = document.getElementById("settingsPanelBody");
const healthBadge = document.getElementById("healthBadge");
const checkModelsHealthBtn = document.getElementById("checkModelsHealthBtn");
const applyModelSettingsBtn = document.getElementById("applyModelSettingsBtn");
const modelHealthResults = document.getElementById("modelHealthResults");
const settingsProviderPriority = document.getElementById("settingsProviderPriority");
const settingsDefaultProvider = document.getElementById("settingsDefaultProvider");
const settingsTaskType = document.getElementById("settingsTaskType");
const settingsTaskProvider = document.getElementById("settingsTaskProvider");
const settingsTaskModel = document.getElementById("settingsTaskModel");

// Toggle settings panel visibility
settingsPanelHeader?.addEventListener("click", () => {
  settingsPanelBody?.classList.toggle("hidden");
});

// Load current settings from the server
async function loadModelSettings() {
  try {
    const res = await fetch("/api/health/models", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    
    // Update health badge
    if (healthBadge && data.summary) {
      const healthy = data.summary.healthy || 0;
      const total = data.summary.total || 0;
      healthBadge.textContent = `${healthy}/${total} online`;
      healthBadge.style.background = healthy > 0 ? "rgba(16, 185, 129, 0.2)" : "rgba(244, 63, 94, 0.2)";
      healthBadge.style.color = healthy > 0 ? "#34d399" : "#f43f5e";
    }
  } catch (err) {
    console.error("Failed to load model settings:", err);
  }
}

// Check models health
checkModelsHealthBtn?.addEventListener("click", async () => {
  if (!modelHealthResults) return;
  modelHealthResults.innerHTML = '<div class="mono small" style="opacity: 0.7;">Checking model health...</div>';
  
  try {
    const res = await fetch("/api/health/models", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    
    // Render health results
    let html = '<div style="font-size: 0.7rem; display: flex; flex-direction: column; gap: 4px;">';
    
    if (data.models) {
      data.models.forEach(m => {
        const statusDot = m.status === "healthy" ? "🟢" : m.status === "error" ? "🔴" : "⚪";
        const latencyStr = m.latency_ms ? `${m.latency_ms}ms` : "-";
        html += `
          <div style="display: flex; align-items: center; gap: 6px; padding: 4px 6px; background: rgba(0,0,0,0.2); border-radius: 4px;">
            <span>${statusDot}</span>
            <span style="font-weight: 600; min-width: 70px;">${m.provider}</span>
            <span style="opacity: 0.7; font-size: 0.65rem; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${m.model || "-"}</span>
            <span style="opacity: 0.5; min-width: 40px; text-align: right;">${latencyStr}</span>
            ${m.error ? `<span style="color: #f43f5e; font-size: 0.6rem;" title="${m.error}">⚠</span>` : ""}
          </div>
        `;
      });
    }
    
    if (data.cost_metrics && Object.keys(data.cost_metrics).length > 0) {
      html += '<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--glass-border);">';
      html += '<div style="font-weight: 600; font-size: 0.65rem; color: var(--muted); margin-bottom: 4px;">Active Run Costs</div>';
      Object.entries(data.cost_metrics).forEach(([runId, metrics]) => {
        html += `<div style="font-size: 0.6rem; opacity: 0.7;">${runId.slice(0, 16)}...: $${metrics.total_cost_usd.toFixed(4)} / $${metrics.budget_usd.toFixed(2)}</div>`;
      });
      html += '</div>';
    }
    
    html += '</div>';
    modelHealthResults.innerHTML = html;
    
    // Update badge
    if (healthBadge && data.summary) {
      healthBadge.textContent = `${data.summary.healthy}/${data.summary.total} online`;
      healthBadge.style.background = data.summary.healthy > 0 ? "rgba(16, 185, 129, 0.2)" : "rgba(244, 63, 94, 0.2)";
      healthBadge.style.color = data.summary.healthy > 0 ? "#34d399" : "#f43f5e";
    }
  } catch (err) {
    modelHealthResults.innerHTML = `<div class="mono small" style="color: #f43f5e;">Error: ${err.message}</div>`;
  }
});

// Apply model settings
applyModelSettingsBtn?.addEventListener("click", async () => {
  const priority = settingsProviderPriority?.value?.trim();
  const defaultProvider = settingsDefaultProvider?.value;
  const taskType = settingsTaskType?.value;
  const taskProvider = settingsTaskProvider?.value?.trim();
  const taskModel = settingsTaskModel?.value?.trim();
  
  // Build the preferences object to send to the memory endpoint
  const preferences = {};
  if (priority) preferences.provider_priority = priority;
  if (defaultProvider) preferences.default_provider = defaultProvider;
  if (taskType && taskProvider) preferences[`task_${taskType}_provider`] = taskProvider;
  if (taskType && taskModel) preferences[`task_${taskType}_model`] = taskModel;
  
  if (Object.keys(preferences).length === 0) return;
  
  try {
    // Store in agent memory
    const targetSessionId = agentSessionId || sessionId || "default";
    await fetch("/api/chat/memory", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_id: targetSessionId,
        preferences: preferences
      })
    });
    
    // Show feedback
    const origText = applyModelSettingsBtn.textContent;
    applyModelSettingsBtn.textContent = "Saved ✓";
    setTimeout(() => { applyModelSettingsBtn.textContent = origText; }, 2000);
  } catch (err) {
    console.error("Failed to save settings:", err);
  }
});


// ── Agent Chat Functions (P15) ─────────────────────────────────────────────────

let agentSessionId = null;
let agentStreamAbortController = null;

const agentSuggestionsEl = document.getElementById("agentSuggestions");
const suggestionsContainerEl = document.getElementById("suggestionsContainer");
const agentCitationsEl = document.getElementById("agentCitations");
const citationsContainerEl = document.getElementById("citationsContainer");
const researchPlanPanelEl = document.getElementById("researchPlanPanel");
const planSectionsContainerEl = document.getElementById("planSectionsContainer");
const planTasksContainerEl = document.getElementById("planTasksContainer");
const planTasksListEl = document.getElementById("planTasksList");
const executePlanBtn = document.getElementById("executePlanBtn");

async function ensureAgentSession() {
  if (agentSessionId) return agentSessionId;
  try {
    const res = await fetch("/api/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ template: templateSelect?.value || "ieee" })
    });
    if (!res.ok) throw new Error("Session creation failed");
    const data = await res.json();
    agentSessionId = data.session_id;
    localStorage.setItem("research_agent_session_id", agentSessionId);
    return agentSessionId;
  } catch (err) {
    console.error("Failed to create agent session:", err);
    return null;
  }
}

function renderCitations(citations) {
  if (!citationsContainerEl || !agentCitationsEl) return;
  if (!citations || citations.length === 0) {
    agentCitationsEl.classList.add("hidden");
    return;
  }
  agentCitationsEl.classList.remove("hidden");
  citationsContainerEl.innerHTML = citations.map((c, i) => {
    const [numPart, ...rest] = c.split("] ");
    const num = numPart.replace("[", "");
    const text = rest.join("] ");
    // Try to extract URL from the citation
    const urlMatch = text.match(/https?:\/\/[^\s]+/);
    const url = urlMatch ? urlMatch[0] : "";
    const displayText = url ? text.replace(url, "").trim() : text;
    return `
      <div class="citation-item">
        <span class="citation-number">${num}</span>
        <span class="citation-text">${displayText}${url ? ` <a href="${url}" target="_blank" rel="noopener">↗</a>` : ""}</span>
      </div>
    `;
  }).join("");
}

function renderSuggestions(suggestions) {
  if (!suggestionsContainerEl || !agentSuggestionsEl) return;
  if (!suggestions || suggestions.length === 0) {
    agentSuggestionsEl.classList.add("hidden");
    return;
  }
  agentSuggestionsEl.classList.remove("hidden");
  suggestionsContainerEl.innerHTML = suggestions.map(s => {
    const text = typeof s === "string" ? s : (s.title || s.query || s);
    const isResearchQuery = typeof s === "string" && (s.toLowerCase().includes("research") || s.toLowerCase().includes("survey") || s.toLowerCase().includes("paper"));
    const dataset = isResearchQuery ? ` data-research="${text.replace(/"/g, "&quot;")}"` : "";
    return `<button class="suggestion-chip" data-query="${text.replace(/"/g, "&quot;")}"${dataset}>${text}</button>`;
  }).join("");
}

// Event delegation for suggestion chips (single consolidated handler)
suggestionsContainerEl?.addEventListener("click", (e) => {
  const chip = e.target.closest(".suggestion-chip");
  if (!chip) return;
  
  // Research-flagged chips get special treatment: trigger research plan generation
  if (chip.dataset.research) {
    const query = chip.dataset.research || chip.textContent;
    if (messageInput) messageInput.value = query;
    chatForm?.dispatchEvent(new Event("submit"));
    return;
  }
  
  const query = chip.dataset.query || chip.textContent;
  if (messageInput) messageInput.value = query;
  chatForm?.dispatchEvent(new Event("submit"));
});

function renderToolCalls(toolCalls) {
  if (!toolCalls || toolCalls.length === 0) return;
  const msgBody = document.querySelector(".message:last-child .message-body");
  if (!msgBody) return;
  const toolContainer = document.createElement("div");
  toolContainer.style.marginTop = "8px";
  toolCalls.forEach(tc => {
    const toolName = tc.tool || "unknown";
    const itemCount = tc.items?.length || 0;
    const error = tc.error;
    const div = document.createElement("div");
    div.className = `tool-call-result ${error ? "tool-error" : "tool-complete"}`;
    div.innerHTML = `
      <span>${error ? "⚠" : "✓"}</span>
      <span><strong>${toolName}</strong>: ${error ? error : `found ${itemCount} results`}</span>
    `;
    toolContainer.appendChild(div);
  });
  msgBody.appendChild(toolContainer);
}

function showAgentThinking() {
  const messagesEl = getMessagesEl();
  if (!messagesEl) return;
  const node = document.createElement("article");
  node.className = "message assistant";
  node.id = "agentThinking";
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><path d="M12 12L2.1 12.1"/></svg>';
  node.appendChild(avatar);
  const msgContent = document.createElement("div");
  msgContent.className = "message-body";
  msgContent.innerHTML = `
    <div class="meta">Research Agent</div>
    <div class="agent-thinking">
      Analyzing your request
      <div class="thinking-dots">
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
      </div>
    </div>
  `;
  node.appendChild(msgContent);
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideAgentThinking() {
  const el = document.getElementById("agentThinking");
  if (el) el.remove();
}

async function loadAgentSuggestions() {
  if (!agentSessionId || !agentSuggestionsEl) return;
  try {
    const res = await fetch(`/api/chat/suggestions?session_id=${encodeURIComponent(agentSessionId)}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    renderSuggestions(data.suggestions || []);
  } catch (err) {
    console.error("Failed to load suggestions:", err);
  }
}

async function renderResearchSuggestions(suggestions) {
  const container = document.getElementById("researchSuggestionsContainer");
  const wrapper = document.getElementById("researchSuggestions");
  const countEl = document.getElementById("researchSuggestionsCount");
  if (!container || !wrapper) return;
  if (!suggestions || suggestions.length === 0) {
    wrapper.classList.add("hidden");
    return;
  }
  wrapper.classList.remove("hidden");
  if (countEl) countEl.textContent = suggestions.length + " topics";
  container.innerHTML = suggestions.map(s => {
    const title = s.title || s.query || "Research topic";
    const domain = s.domain || "";
    const reason = s.reason || "";
    const query = s.query || title;
    const type = s.type || "trending";
    const domainColors = {
      "NLP": "#06b6d4", "AI": "#8b5cf6", "NLP/IR": "#06b6d4",
      "Multimodal": "#f59e0b", "Efficiency": "#10b981",
      "Safety": "#f43f5e", "Science": "#3b82f6", "ML Theory": "#a78bfa",
      "past_research": "#34d399", "agent_memory": "#c4b5fd",
      "literature_monitoring": "#f0abfc"
    };
    const dotColor = domainColors[domain] || "#71717a";
    const typeLabels = { "trending": "\ud83d\udd25", "past_topic": "\ud83d\udcdc",
      "memory_topic": "\ud83e\udde0", "watchdog_topic": "\ud83d\udc40" };
    const icon = typeLabels[type] || "\ud83d\udd0d";
    return `
      <button class="research-suggestion-card" data-query="${query.replace(/"/g, '&quot;')}" title="${reason.replace(/"/g, '&quot;')}">
        <span class="research-suggestion-icon">${icon}</span>
        <div class="research-suggestion-body">
          <span class="research-suggestion-title">${title}</span>
          <span class="research-suggestion-reason">${reason}</span>
        </div>
        <span class="research-suggestion-dot" style="background: ${dotColor};"></span>
      </button>
    `;
  }).join("");
}

async function loadResearchSuggestions() {
  try {
    const res = await fetch("/api/research/suggestions", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    renderResearchSuggestions(data.suggestions || []);
  } catch (err) {
    console.error("Failed to load research suggestions:", err);
  }
}

// Click delegation for research suggestion cards
document.addEventListener("click", (e) => {
  const card = e.target.closest(".research-suggestion-card");
  if (!card) return;
  const query = card.dataset.query || card.textContent;
  if (messageInput) {
    messageInput.value = query;
    chatForm?.dispatchEvent(new Event("submit"));
  }
});

async function runAgentChatFlow(message) {
  const sid = await ensureAgentSession();
  if (!sid) {
    appendMessage("assistant", "Failed to create session. Please try again.");
    return;
  }

  appendMessage("user", message);
  showAgentThinking();
  if (sendBtn) sendBtn.disabled = true;

  // Hide previous suggestions/citations
  if (agentSuggestionsEl) agentSuggestionsEl.classList.add("hidden");
  if (agentCitationsEl) agentCitationsEl.classList.add("hidden");

  try {
    const res = await fetch("/api/chat/agent", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_id: sid,
        message: message
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Agent request failed");
    }

    const data = await res.json();
    hideAgentThinking();

    // Show the response
    const options = {};
    // If there's a research launch topic, add a launch button
    const hasResearch = (data.tool_calls || []).some(tc => tc.tool === "launch_research");
    if (hasResearch) {
      options.links = {
        "Launch Full Research": "#"
      };
    }
    appendMessage("assistant", data.message || "No response received.");

    // Render tool calls
    renderToolCalls(data.tool_calls || []);

    // Show citations
    renderCitations(data.citations || []);

    // Show suggestions
    renderSuggestions(data.suggestions || []);

    // Add launch research button if topic was discussed
    const lastMsg = document.querySelector(".message:last-child .message-body");
    if (lastMsg && data.tool_calls?.some(tc => tc.tool === "launch_research")) {
      const launchBtn = document.createElement("button");
      launchBtn.className = "launch-research-btn";
      launchBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg> Launch Full Research Paper';
      launchBtn.onclick = async () => {
        launchBtn.disabled = true;
        launchBtn.textContent = "Launching...";
        try {
          const lr = await fetch("/api/chat/launch-research", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ topic: message, session_id: sid })
          });
          const lrData = await lr.json();
          if (lrData.kind === "result") {
            currentRunId = lrData.run_id;
            appendMessage("assistant", `🚀 Research launched! Paper: "${lrData.topic}" (${lrData.section_count} sections). Check the Document Editor tab.`, {
              links: {
                "View Artifacts": `/api/runs/${lrData.run_id}/graph`,
                "Download PDF": lrData.artifact_urls?.pdf
              }
            });
            if (currentRunId && overleafPushBtn) overleafPushBtn.classList.remove("hidden");
            setWorkbenchStatus("ready", "success");
            updatePipelineTracker("completed");
            switchWorkbenchTab("doc");
          } else {
            appendMessage("assistant", `Clarification needed: ${(lrData.questions || []).join(", ")}`);
          }
        } catch (err) {
          appendMessage("assistant", `Research launch failed: ${err.message}`);
        }
      };
      lastMsg.appendChild(launchBtn);
    }
  } catch (err) {
    hideAgentThinking();
    appendMessage("assistant", `Error: ${err.message}`);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (messageInput) messageInput.focus();
  }
}

async function runAgentChatStreamFlow(message) {
  const sid = await ensureAgentSession();
  if (!sid) {
    appendMessage("assistant", "Failed to create session.");
    return;
  }

  appendMessage("user", message);
  if (sendBtn) sendBtn.disabled = true;
  if (agentSuggestionsEl) agentSuggestionsEl.classList.add("hidden");
  if (agentCitationsEl) agentCitationsEl.classList.add("hidden");

  // Create assistant message node that we'll update
  const assistantNode = appendMessage("assistant", "", { generating: true });
  const textContent = assistantNode?.querySelector(".text-content");
  const msgBody = assistantNode?.querySelector(".message-body");
  let fullMessage = "";
  const toolContainer = document.createElement("div");
  toolContainer.style.marginTop = "8px";
  if (msgBody) msgBody.appendChild(toolContainer);

  agentStreamAbortController = new AbortController();

  try {
    const res = await fetch("/api/chat/agent/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_id: sid,
        message: message
      }),
      signal: agentStreamAbortController.signal
    });

    if (!res.ok) {
      throw new Error("Stream request failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const event = JSON.parse(line);

          switch (event.event) {
            case "thought":
              if (textContent) textContent.textContent = "🧠 " + (event.content || "Thinking...");
              break;

            case "tool_result":
              const tcDiv = document.createElement("div");
              tcDiv.className = `tool-call-result ${event.status === "error" ? "tool-error" : "tool-complete"}`;
              tcDiv.innerHTML = `<span>${event.status === "error" ? "⚠" : "✓"}</span><span><strong>${event.tool}</strong>: ${event.status === "error" ? event.error : `${event.item_count} results`}</span>`;
              toolContainer.appendChild(tcDiv);
              break;

            case "complete":
              if (textContent) {
                textContent.textContent = event.message || "";
              }
              renderCitations(event.citations || []);
              renderSuggestions(event.suggestions || []);
              
              // Add launch research button
              if (event.suggestions?.some(s => typeof s === "string" && s.toLowerCase().includes("research"))) {
                const launchBtn = document.createElement("button");
                launchBtn.className = "launch-research-btn";
                launchBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg> Launch Full Research';
                launchBtn.onclick = async () => {
                  launchBtn.disabled = true;
                  launchBtn.textContent = "Launching...";
                  try {
                    const lr = await fetch("/api/chat/launch-research", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${authToken}`
                      },
                      body: JSON.stringify({ topic: message, session_id: sid })
                    });
                    const lrData = await lr.json();
                    if (lrData.kind === "result") {
                      currentRunId = lrData.run_id;
                      appendMessage("assistant", `🚀 Research paper launched on "${lrData.topic}"! Check the Document Editor.`);
                      if (currentRunId && overleafPushBtn) overleafPushBtn.classList.remove("hidden");
                      setWorkbenchStatus("ready", "success");
                      switchWorkbenchTab("doc");
                    }
                  } catch (err) {
                    console.error("Launch research failed:", err);
                  }
                };
                if (msgBody) msgBody.appendChild(launchBtn);
              }
              break;

            case "error":
              if (textContent) textContent.textContent = `Error: ${event.message}`;
              break;
          }
        } catch (e) {
          console.warn("Failed to parse stream event:", line, e);
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    if (textContent) textContent.textContent = `Error: ${err.message}`;
  } finally {
    agentStreamAbortController = null;
    if (sendBtn) sendBtn.disabled = false;
    if (messageInput) messageInput.focus();
    // Remove generating indicator
    if (assistantNode) {
      const typing = assistantNode.querySelector(".typing");
      if (typing) typing.remove();
    }
  }
}

// Patch appendMessage to add feedback buttons to assistant messages
const _originalAppendMessage = appendMessage;
let _messageIndex = 0;

appendMessage = function(role, text, options = {}) {
  const node = _originalAppendMessage(role, text, options);
  if (role === "assistant" && agentSessionId) {
    _messageIndex++;
    addFeedbackButtons(node, agentSessionId, _messageIndex);
  }
  return node;
};

// Update mode handler for agent chat
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
    } else if (mode === "agent") {
      messageInput.placeholder = "Ask me anything! Find papers, search web, discover datasets...";
      loadAgentSuggestions();
    }
  });
});

// Patch the chat form submit to handle agent mode and research planning
chatForm?.addEventListener("submit", async (e) => {
  const activeMode = document.querySelector('input[name="runMode"]:checked')?.value || "paper";
  if (activeMode === "agent") {
    e.preventDefault();
    const text = messageInput?.value.trim();
    if (!text) return;
    messageInput.value = "";

    // Check if this looks like a research intent (generate a plan first)
    const researchPatterns = ["write", "research", "paper on", "survey on", "create a paper", "generate a paper", "write a survey", "write about"];
    const isResearchIntent = researchPatterns.some(p => text.toLowerCase().startsWith(p) || text.toLowerCase().includes(p));

    if (isResearchIntent) {
      // Extract the actual topic from research intent patterns
      let topic = text;
      for (const pattern of researchPatterns) {
        const idx = text.toLowerCase().indexOf(pattern);
        if (idx >= 0) {
          const afterPattern = text.substring(idx + pattern.length).trim();
          if (afterPattern && afterPattern.length > 5) {
            topic = afterPattern.replace(/^"|"$/g, "").replace(/^on\s+/i, "");
            break;
          }
        }
      }
      await generateResearchPlan(topic);
    } else {
      // Use streaming by default, fallback to non-streaming
      try {
        await runAgentChatStreamFlow(text);
      } catch (err) {
        console.warn("Streaming agent chat failed, falling back to non-streaming:", err);
        await runAgentChatFlow(text);
      }
    }
  }
  // Otherwise the existing handler (via onsubmit) or the previous listener will handle it
}, true);  // Use capture to run before other handlers



(async () => {
  resetWorkbench();
  checkAuth();
  
  // Restore agent session if exists
  const savedAgentSession = localStorage.getItem("research_agent_session_id");
  if (savedAgentSession) {
    agentSessionId = savedAgentSession;
  }

  // Load model settings and health status on startup
  setTimeout(() => loadModelSettings(), 2000);
  setTimeout(() => loadWatchdogDigests(), 3000);
})();


// ── P26: Hypothesis & Strategy Panel Renderers ──────────────────────────────

function renderHypotheses(hypotheses) {
  const panel = document.getElementById("hypothesisPanel");
  const badge = document.getElementById("hypothesisBadge");
  if (!panel) return;
  if (!hypotheses || hypotheses.length === 0) {
    panel.innerHTML = '<p class="small muted">No hypotheses generated yet.</p>';
    if (badge) badge.textContent = "0";
    return;
  }
  if (badge) badge.textContent = hypotheses.length;
  panel.innerHTML = hypotheses.map((h, idx) => {
    const noveltyScore = (h.novelty_score || 0) * 100;
    const feasibilityScore = (h.feasibility_score || 0) * 100;
    const gapLabel = h.gap_addressed || "general";
    const gapColors = { "methodology": "#8b5cf6", "evaluation": "#06b6d4", "coverage": "#10b981", "general": "#71717a" };
    const gapColor = gapColors[gapLabel] || "#71717a";
    return `
      <div class="p26-card hypothesis-card" style="animation-delay: ${idx * 0.05}s">
        <div class="p26-card-header">
          <span class="p26-card-title">${h.title || "Hypothesis " + (idx + 1)}</span>
          <span class="p26-gap-badge" style="background: ${gapColor}22; border-color: ${gapColor}44; color: ${gapColor};">${gapLabel}</span>
        </div>
        <div class="p26-card-body">
          <p class="p26-hypothesis-statement">${h.hypothesis || ""}</p>
          <p class="p26-hypothesis-rationale">${h.rationale || ""}</p>
        </div>
        <div class="p26-card-scores">
          <div class="p26-score-bar">
            <span class="p26-score-label">Novelty</span>
            <div class="p26-score-track">
              <div class="p26-score-fill" style="width: ${noveltyScore}%; background: linear-gradient(90deg, #8b5cf6, #a78bfa);"></div>
            </div>
            <span class="p26-score-value">${Math.round(noveltyScore)}%</span>
          </div>
          <div class="p26-score-bar">
            <span class="p26-score-label">Feasibility</span>
            <div class="p26-score-track">
              <div class="p26-score-fill" style="width: ${feasibilityScore}%; background: linear-gradient(90deg, #10b981, #34d399);"></div>
            </div>
            <span class="p26-score-value">${Math.round(feasibilityScore)}%</span>
          </div>
        </div>
        ${h.proposed_approach ? `<div class="p26-card-detail"><strong>Approach:</strong> ${h.proposed_approach}</div>` : ""}
        ${h.evaluation_approach ? `<div class="p26-card-detail"><strong>Evaluation:</strong> ${h.evaluation_approach}</div>` : ""}
        ${h.required_resources && h.required_resources.length > 0 ? `
          <div class="p26-card-tags">
            ${h.required_resources.map(r => `<span class="p26-tag">${r}</span>`).join("")}
          </div>
        ` : ""}
      </div>
    `;
  }).join("");
}

function renderStrategy(strategy) {
  const panel = document.getElementById("strategyPanel");
  const badge = document.getElementById("strategyBadge");
  if (!panel) return;
  if (!strategy || !strategy.methodology) {
    panel.innerHTML = '<p class="small muted">No strategy recommendations yet.</p>';
    if (badge) badge.textContent = "Ready";
    return;
  }
  if (badge) badge.textContent = "Ready";
  let html = "";

  // Methodology
  if (strategy.methodology) {
    html += '<div class="p26-section-label">Methodology</div>';
    if (strategy.methodology.recommended_approaches) {
      strategy.methodology.recommended_approaches.forEach(a => {
        html += \`
          <div class="p26-card">
            <div class="p26-card-header">
              <span class="p26-card-title-small">\${a.name || ""}</span>
            </div>
            <div class="p26-card-body">
              <p class="p26-card-desc">\${a.description || ""}</p>
              \${a.rationale ? \`<p class="p26-card-rationale">\${a.rationale}</p>\` : ""}
            </div>
          </div>
        \`;
      });
    }
    if (strategy.methodology.avoid && strategy.methodology.avoid.length > 0) {
      html += '<div class="p26-card-avoid">';
      html += '<span class="p26-avoid-label">Avoid</span>';
      strategy.methodology.avoid.forEach(a => {
        html += \`<span class="p26-avoid-chip">\${a}</span>\`;
      });
      html += '</div>';
    }
  }

  // Datasets
  if (strategy.datasets && strategy.datasets.recommended) {
    html += '<div class="p26-section-label" style="margin-top: 8px;">Datasets</div>';
    strategy.datasets.recommended.forEach(d => {
      html += \`
        <div class="p26-card p26-card-compact">
          <span class="p26-card-title-small">\${d.name || ""}</span>
          <p class="p26-card-desc">\${d.description || ""}</p>
        </div>
      \`;
    });
  }

  // Baselines
  if (strategy.baselines && strategy.baselines.recommended) {
    html += '<div class="p26-section-label" style="margin-top: 8px;">Baselines</div>';
    strategy.baselines.recommended.forEach(b => {
      html += \`
        <div class="p26-card p26-card-compact">
          <span class="p26-card-title-small">\${b.name || ""}</span>
          <p class="p26-card-desc">\${b.description || ""}</p>
        </div>
      \`;
    });
  }

  // Evaluation
  if (strategy.evaluation) {
    html += '<div class="p26-section-label" style="margin-top: 8px;">Evaluation</div>';
    if (strategy.evaluation.primary_metrics) {
      html += '<div class="p26-card-tags">' +
        strategy.evaluation.primary_metrics.map(m => \`<span class="p26-tag">\${m}</span>\`).join("") +
        '</div>';
    }
    if (strategy.evaluation.ablation) {
      html += '<div class="p26-card-detail" style="margin-top: 4px;"><strong>Ablation:</strong> ' +
        (Array.isArray(strategy.evaluation.ablation) ? strategy.evaluation.ablation.join("; ") : strategy.evaluation.ablation) +
        '</div>';
    }
  }

  panel.innerHTML = html;
}

function renderGapExploration(gapExp) {
  if (!gapExp || !gapExp.is_thin) return;
  const panel = document.getElementById("hypothesisPanel");
  if (!panel) return;
  // Add gap exploration note at the top of the hypothesis panel
  const note = document.createElement("div");
  note.className = "p26-card p26-thin-note";
  note.innerHTML = \`
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
      <span style="font-size: 1rem;">\u26a0\ufe0f</span>
      <span style="font-weight: 600; font-size: 0.75rem; color: #f59e0b;">Thin Literature Detected</span>
    </div>
    <p style="font-size: 0.7rem; color: #a1a1aa; margin: 0; line-height: 1.4;">\${gapExp.analysis || ""}</p>
    <div style="display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap;">
      \${(gapExp.alternative_queries || []).map(q => \`<span class="p26-tag p26-tag-alt">\${q}</span>\`).join("")}
    </div>
    <div style="margin-top: 6px; font-size: 0.65rem; color: #f59e0b; font-weight: 600; text-transform: uppercase;">
      Recommendation: \${(gapExp.recommendation || "").replace(/_/g, " ")}
    </div>
  \`;
  panel.insertBefore(note, panel.firstChild);
}

// ── Watchdog Dashboard Widget (P13) ──────────────────────────────

const watchdogPanelHeader = document.getElementById("watchdogPanelHeader");
const watchdogDigests = document.getElementById("watchdogDigests");
const watchdogBadge = document.getElementById("watchdogBadge");
const watchdogRefreshBtn = document.getElementById("watchdogRefreshBtn");
const watchdogCheckNowBtn = document.getElementById("watchdogCheckNowBtn");

// Toggle watchdog panel visibility (always visible, just the header is clickable)
watchdogPanelHeader?.addEventListener("click", () => {
  // Could toggle expanded view, but keep it always shown for dashboard
});

async function loadWatchdogDigests() {
  if (!watchdogDigests) return;
  try {
    const res = await fetch("/api/watchdog/dashboard", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) {
      watchdogDigests.innerHTML = '<p class="small muted">Login to see papers</p>';
      return;
    }
    const data = await res.json();
    
    // Update badge
    if (watchdogBadge) {
      const totalNew = data.total_new_papers || 0;
      const active = data.active_subscriptions || 0;
      watchdogBadge.textContent = `${active} subs`;
      watchdogBadge.style.background = totalNew > 0 ? "rgba(52, 211, 153, 0.2)" : "rgba(255,255,255,0.05)";
      watchdogBadge.style.color = totalNew > 0 ? "#34d399" : "var(--muted)";
    }
    
    // Render digests
    let html = "";
    
    // Show subscriptions summary
    if (data.active_subscriptions > 0) {
      html += `<div style="font-size: 0.6rem; color: #71717a; margin-bottom: 6px; display: flex; justify-content: space-between;">
        <span>${data.active_subscriptions} active sub${data.active_subscriptions !== 1 ? 's' : ''}</span>
        <span style="font-weight: 600; color: ${data.total_new_papers > 0 ? '#34d399' : '#71717a'};">${data.total_new_papers} new</span>
      </div>`;
    }
    
    // Show recent digests
    const digests = data.recent_digests || [];
    if (digests.length === 0) {
      if (data.active_subscriptions > 0) {
        html += '<p class="small muted">Waiting for next check...</p>';
      } else {
        html += '<p class="small muted">No subscriptions yet. Use Agent Chat or Watchdog API.</p>';
      }
    } else {
      digests.slice(0, 3).forEach(d => {
        const timeAgo = getTimeAgo(d.generated_at);
        html += `<div class="discovery-item" style="cursor: pointer;" onclick="openWatchdogDigest('${d.digest_id}')">
          <span class="source">${d.topic}${d.email_sent ? ' ✉' : ''}</span>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>${d.paper_count} paper${d.paper_count !== 1 ? 's' : ''}${d.summary ? ': ' + d.summary.substring(0, 60) : ''}</span>
            <span style="font-size: 0.6rem; color: #52525b;">${timeAgo}</span>
          </div>
        </div>`;
      });
    }
    
    watchdogDigests.innerHTML = html;
  } catch (err) {
    console.error("Failed to load watchdog digests:", err);
    watchdogDigests.innerHTML = '<p class="small muted">Could not load digests</p>';
  }
}

function getTimeAgo(timestamp) {
  const now = Date.now() / 1000;
  const diff = now - timestamp;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function openWatchdogDigest(digestId) {
  // Switch to the digests tab in the existing watchdog display
  if (watchdogDigests) {
    // Highlight the selected digest — could load full details
    console.log("Selected digest:", digestId);
  }
}

// Refresh watchdog digests
watchdogRefreshBtn?.addEventListener("click", () => {
  loadWatchdogDigests();
});

// Trigger manual check
watchdogCheckNowBtn?.addEventListener("click", async () => {
  if (!watchdogDigests) return;
  watchdogDigests.innerHTML = '<p class="small muted">Checking all subscriptions...</p>';
  try {
    const res = await fetch("/api/watchdog/check", {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Check failed");
    const data = await res.json();
    watchdogDigests.innerHTML = `<p class="small muted">Checked ${data.profiles_checked || 0} subscription${data.profiles_checked !== 1 ? 's' : ''}. ${data.total_new_papers || 0} new papers found.</p>`;
    setTimeout(() => loadWatchdogDigests(), 2000);
  } catch (err) {
    watchdogDigests.innerHTML = `<p class="small muted">Error: ${err.message}</p>`;
    setTimeout(() => loadWatchdogDigests(), 3000);
  }
});


// ── P27: Submission Pipeline Functions ──────────────────────────────────

const submissionStatusText = document.getElementById("submissionStatusText");
const submissionResults = document.getElementById("submissionResults");
const submissionScore = document.getElementById("submissionScore");
const submissionErrors = document.getElementById("submissionErrors");
const submissionWarnings = document.getElementById("submissionWarnings");
const submissionInfoCount = document.getElementById("submissionInfoCount");
const submissionIssuesList = document.getElementById("submissionIssuesList");
const submissionExportOptions = document.getElementById("submissionExportOptions");
const submissionFormatSelect = document.getElementById("submissionFormatSelect");
const submissionEmptyState = document.getElementById("submissionEmptyState");
const submissionRunCheckBtn = document.getElementById("submissionRunCheckBtn");
const submissionRunPipelineBtn = document.getElementById("submissionRunPipelineBtn");

async function loadSubmissionPipeline() {
  if (!currentRunId) {
    if (submissionEmptyState) submissionEmptyState.style.display = "flex";
    if (submissionResults) submissionResults.classList.add("hidden");
    if (submissionStatusText) submissionStatusText.textContent = "No active run loaded yet.";
    return;
  }

  if (submissionEmptyState) submissionEmptyState.style.display = "none";
  if (submissionStatusText) submissionStatusText.textContent = "Loading paper data...";
  if (submissionResults) submissionResults.classList.remove("hidden");

  try {
    var tex = localStorage.getItem("run_latex_" + currentRunId) || "";
    if (!tex) {
      if (submissionStatusText) submissionStatusText.textContent = "No LaTeX content available. Generate a paper first.";
      return;
    }

    if (submissionStatusText) submissionStatusText.textContent = "Running checks...";
    var format = submissionFormatSelect ? submissionFormatSelect.value : "ieee";

    var checkRes = await fetch("/api/submission/style-check", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: JSON.stringify({ tex: tex, format: format })
    });

    if (!checkRes.ok) throw new Error("Style check failed");
    var checkData = await checkRes.json();

    var scorePct = Math.round((checkData.score || 0) * 100);
    if (submissionScore) submissionScore.textContent = scorePct + "%";
    if (submissionScore) submissionScore.style.color = scorePct >= 80 ? "#34d399" : scorePct >= 50 ? "#f59e0b" : "#f43f5e";
    if (submissionErrors) submissionErrors.textContent = checkData.errors || 0;
    if (submissionWarnings) submissionWarnings.textContent = checkData.warnings || 0;
    if (submissionInfoCount) submissionInfoCount.textContent = checkData.info || 0;

    if (submissionStatusText) submissionStatusText.textContent = checkData.passed ? "All checks passed!" : checkData.errors + " errors found";

    var issues = checkData.issues || [];
    if (submissionIssuesList) {
      if (issues.length === 0) {
        submissionIssuesList.innerHTML = '<div style="padding: 12px; text-align: center; color: #34d399;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> All checks passed!</div>';
      } else {
        submissionIssuesList.innerHTML = issues.map(function(i) {
          var sev = i.severity || "info";
          var icon = sev === "error" ? "\u274c" : sev === "warning" ? "\u26a0\ufe0f" : "\u2139\ufe0f";
          var color = sev === "error" ? "#f43f5e" : sev === "warning" ? "#f59e0b" : "#71717a";
          return (
            '<div style="display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); font-size: 0.78rem;">' +
              '<span style="font-size: 0.85rem; line-height: 1.4;">' + icon + "</span>" +
              '<div style="flex: 1; min-width: 0;">' +
                '<div style="font-weight: 600; color: ' + color + '; margin-bottom: 2px;">' + i.message + "</div>" +
                (i.detail ? '<div style="opacity: 0.6; font-size: 0.7rem;">' + i.detail + "</div>" : "") +
              "</div>" +
            "</div>"
          );
        }).join("");
      }
    }

    if (submissionExportOptions) {
      submissionExportOptions.innerHTML =
        '<button id="submissionDownloadTexBtn" class="btn-icon" type="button" style="padding: 8px 14px; border: 1px solid var(--glass-border); border-radius: var(--radius-sm);">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> Download .tex' +
        '</button>' +
        '<button id="submissionDownloadZipBtn" class="btn-icon" type="button" style="margin-left: 6px; padding: 8px 14px; border: 1px solid var(--glass-border); border-radius: var(--radius-sm);">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> Download ZIP' +
        '</button>';

      setTimeout(function() {
        var downloadBtn = document.getElementById("submissionDownloadTexBtn");
        if (downloadBtn) {
          downloadBtn.addEventListener("click", function() {
            var blob = new Blob([tex], { type: "application/x-latex" });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = "paper-" + format + ".tex";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
          });
        }
        var zipBtn = document.getElementById("submissionDownloadZipBtn");
        if (zipBtn) {
          zipBtn.addEventListener("click", async function() {
            try {
              var zipRes = await fetch("/api/submission/export-zip/" + currentRunId + "?format=" + format, {
                headers: { "Authorization": "Bearer " + authToken }
              });
              if (!zipRes.ok) throw new Error("ZIP export failed");
              var blob = await zipRes.blob();
              var url = URL.createObjectURL(blob);
              var a = document.createElement("a");
              a.href = url;
              a.download = "paper-" + format + ".zip";
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } catch (err) {
              console.error("ZIP download failed:", err);
            }
          });
        }
      }, 100);
    }

  } catch (err) {
    console.error("Submission pipeline error:", err);
    if (submissionStatusText) submissionStatusText.textContent = "Error: " + err.message;
  }
}

// Format change handler
document.addEventListener("change", function(e) {
  if (e.target && e.target.id === "submissionFormatSelect") {
    var resultsVisible = document.getElementById("submissionResults");
    if (resultsVisible && !resultsVisible.classList.contains("hidden")) {
      loadSubmissionPipeline();
    }
  }
});

// Run check button
if (submissionRunCheckBtn) submissionRunCheckBtn.addEventListener("click", loadSubmissionPipeline);

// Full pipeline button
if (submissionRunPipelineBtn) {
  submissionRunPipelineBtn.addEventListener("click", async function() {
    if (!currentRunId) return;
    var tex = localStorage.getItem("run_latex_" + currentRunId);
    if (!tex) return;
    var btn = submissionRunPipelineBtn;
    btn.disabled = true;
    btn.textContent = "Running...";
    try {
      var format = submissionFormatSelect ? submissionFormatSelect.value : "ieee";
      var res = await fetch("/api/submission/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
        body: JSON.stringify({ tex: tex, format: format, check_only: false })
      });
      if (res.ok) {
        loadSubmissionPipeline();
      }
    } catch (err) {
      console.error("Pipeline error:", err);
    } finally {
      btn.disabled = false;
      btn.textContent = "Full Pipeline";
    }
  });
}

// ── End of Submission Pipeline ───────────────────────────────────────────
