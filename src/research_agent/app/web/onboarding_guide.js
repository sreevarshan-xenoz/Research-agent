// ── P38: Interactive Tutorial & Onboarding ───────────────────────────────────
// Features: Guided tour, sample topics, contextual tooltips, welcome overlay

(function() {
  'use strict';

  const ONBOARDING_KEY = "research_onboarding_completed_v1";

  // ── Tour Steps ──────────────────────────────────────────────────────────
  const TOUR_STEPS = [
    {
      target: ".sidebar-header",
      title: "Welcome to Research Agent!",
      content: "This is your research command center. Configure templates, depth, and autonomy settings here. Let's take a quick tour of the key areas.",
      placement: "right",
      onEnter: function() { setWorkbenchStatus?.("idle", "Tour: Startup"); }
    },
    {
      target: ".pipeline-tracker",
      title: "Research Pipeline",
      content: "Watch your research progress through 5 stages: Intake → Planning → Researching → Verification → Composing. Each step lights up as it completes.",
      placement: "bottom"
    },
    {
      target: ".workbench-tabs",
      title: "Workbench Tabs",
      content: "Each tab opens a different view: Document Editor, LaTeX Source, PDF Preview, Blog Export, Citation Graph, Datasets, Grant Proposals, Trends, and Reproducibility Dashboard.",
      placement: "bottom"
    },
    {
      target: "#docWorkbench",
      title: "Document Editor",
      content: "Your generated research paper appears here as formatted HTML. You can edit it directly using the Quill editor toolbar above.",
      placement: "left"
    },
    {
      target: "#latexWorkbench",
      title: "LaTeX Source",
      content: "The raw LaTeX source streams in real-time as the AI writes. You can copy, edit, or push this directly to Overleaf.",
      placement: "left"
    },
    {
      target: "#previewWorkbench",
      title: "PDF Preview",
      content: "Click 'Compile PDF' to render your LaTeX into a downloadable PDF. Great for seeing how your paper will look when published.",
      placement: "left"
    },
    {
      target: ".chat-area",
      title: "Research Chat",
      content: "This is your main control center. Type a research topic, select a mode (Paper, Survey, Library Q&A, or Agent Chat), and hit Send to launch research.",
      placement: "left"
    },
    {
      target: ".composer-modes",
      title: "Research Modes",
      content: "Choose from 4 modes: Research Paper (full paper generation), Literature Survey (multi-paper synthesis), Library Q&A (ask questions about uploaded PDFs), or Agent Chat (tool-calling AI assistant).",
      placement: "top"
    },
    {
      target: ".config-panel",
      title: "Configuration Settings",
      content: "Fine-tune your research: choose a LaTeX template (IEEE/ACM/Springer), language, research depth (Quick/Balanced/Deep), autonomy level, runtime limit, and cost budget.",
      placement: "right"
    },
    {
      target: ".kanban-wrapper",
      title: "Task Board",
      content: "See real-time progress of your research tasks across Pending, Active, and Done columns. Each card shows which agent is working on what.",
      placement: "right"
    },
    {
      target: ".sidebar-actions",
      title: "Session Controls",
      content: "Start a new session to reset, or stop a running research task anytime. Your session persists across page reloads.",
      placement: "right",
      isLast: true
    }
  ];

  // ── Sample Topics ───────────────────────────────────────────────────────
  const SAMPLE_TOPICS = [
    {
      title: "Transformer Architectures",
      subtitle: "Survey of attention mechanisms and position encodings",
      topic: "A comparative analysis of transformer architectures: from original attention to modern efficient variants",
      template: "ieee-2col",
      depth: "balanced",
      mode: "paper"
    },
    {
      title: "RL for Robotics",
      subtitle: "Deep reinforcement learning applications in robotic manipulation",
      topic: "Deep reinforcement learning for robotic manipulation: algorithms, sim-to-real transfer, and open challenges",
      template: "ieee-2col",
      depth: "balanced",
      mode: "paper"
    },
    {
      title: "Diffusion Models",
      subtitle: "Denoising diffusion probabilistic models for image generation",
      topic: "Diffusion models for image generation: from DDPM to latent diffusion and beyond",
      template: "ieee-2col",
      depth: "deep",
      mode: "paper"
    },
    {
      title: "LLM Reasoning",
      subtitle: "Chain-of-thought and reasoning techniques in LLMs",
      topic: "Chain-of-thought reasoning in large language models: techniques, benchmarks, and limitations",
      template: "ieee-2col",
      depth: "balanced",
      mode: "survey"
    },
    {
      title: "NLP Trends",
      subtitle: "Recent developments in natural language processing",
      topic: "Recent advances in natural language processing: from BERT to GPT-4 and open-source LLMs",
      template: "ieee-2col",
      depth: "quick",
      mode: "survey"
    },
    {
      title: "Graph Neural Networks",
      subtitle: "GNN architectures for molecular and social network analysis",
      topic: "Graph neural networks for molecular property prediction and social network analysis",
      template: "acm",
      depth: "balanced",
      mode: "paper"
    }
  ];

  // ── Tooltip Definitions ─────────────────────────────────────────────────
  // Format: [selector, title, description]
  const TOOLTIPS = [
    ["#templateSelect", "Template", "Choose IEEE, ACM, Springer, or custom LaTeX templates for your paper."],
    ["#depthSelect", "Depth", "Quick (~2 min), Balanced (~8 min), or Deep (~20 min) research."],
    ["#autonomySelect", "Autonomy", "Guided (asks questions), Hybrid (semi-autonomous), or Autonomous (full auto)."],
    ["#runtimeCapInput", "Max Runtime", "Maximum minutes the AI spends on research before stopping."],
    ["#costCapInput", "Cost Budget", "Maximum API cost budget in USD for the research run."],
    ["#sendBtn", "Send / Launch", "Start research on your entered topic using the selected mode."],
    ["#newSessionBtn", "New Session", "Reset the current session and start fresh."],
    ["#stopRunBtn", "Stop Run", "Interrupt and cancel the currently running research task."],
    ["#docTabBtn", "Document Editor", "View and edit the generated paper as formatted HTML."],
    ["#latexTabBtn", "LaTeX Source", "View the raw LaTeX code the AI is generating."],
    ["#previewTabBtn", "PDF Preview", "Compile and preview your paper as a PDF."],
    ["#blogTabBtn", "Blog & Social", "Export your research as blog posts, newsletters, or Twitter threads."],
    ["#citationTabBtn", "Citation Graph", "Visualize the citation network of papers used in your research."],
    ["#datasetsTabBtn", "Datasets", "Discover relevant datasets from HuggingFace and Kaggle."],
    ["#proposalTabBtn", "Grant Proposal", "Generate a funding proposal based on your research."],
    ["#trendsTabBtn", "Research Trends", "Analyze publication trends, top authors, and keywords."],
    ["#reproducibilityTabBtn", "Reproducibility", "Verify empirical claims from your paper with code execution."],
    ["#overleafPushBtn", "Push to Overleaf", "Send your LaTeX project directly to Overleaf for collaborative editing."],
    ["#renderPdfBtn", "Compile PDF", "Render your LaTeX source into a downloadable PDF file."],
    ["#generateBlogBtn", "Generate Blog", "Create blog posts, newsletters, and Twitter threads from your research."],
    ["#generateProposalBtn", "Generate Proposal", "Create a structured grant proposal from your research output."],
    ["#searchTrendsBtn", "Analyze Trends", "Search for publication trends on a research topic."],
    ["#runModeRadios", "Research Mode", "Toggle between Paper, Survey, Library Q&A, and Agent Chat modes."]
  ];

  // ── State ───────────────────────────────────────────────────────────────
  let _tourActive = false;
  let _currentStep = 0;
  let _tourOverlay = null;
  let _tourTooltip = null;
  let _onboardingComplete = false;

  // ── Initialize ──────────────────────────────────────────────────────────
  function init() {
    _onboardingComplete = localStorage.getItem(ONBOARDING_KEY) === "true";

    // Only create elements after DOM is ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", _onDOMReady);
    } else {
      _onDOMReady();
    }
  }

  function _onDOMReady() {
    createTourElements();
    createTooltipElements();
    createSampleTopicsPanel();

    // Show welcome overlay for first-time users
    if (!_onboardingComplete) {
      showWelcomeOverlay();
    }
  }

  // ── Welcome Overlay ────────────────────────────────────────────────────
  function showWelcomeOverlay() {
    const overlay = document.createElement("div");
    overlay.id = "onboardingWelcomeOverlay";
    overlay.className = "onboarding-welcome-overlay";
    overlay.innerHTML = `
      <div class="onboarding-welcome-card">
        <div class="onboarding-welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
          </svg>
        </div>
        <h1 class="onboarding-welcome-title">Welcome to Research Agent</h1>
        <p class="onboarding-welcome-subtitle">Your AI-powered research assistant for generating papers, surveys, and academic content.</p>
        <div class="onboarding-welcome-actions">
          <button id="onboardingStartTourBtn" class="onboarding-btn primary">Take the Tour</button>
          <button id="onboardingExploreBtn" class="onboarding-btn secondary">Start Exploring</button>
          <button id="onboardingSampleTopicsBtn" class="onboarding-btn tertiary">Browse Sample Topics</button>
        </div>
        <div class="onboarding-welcome-features">
          <div class="onboarding-feature-item">
            <span class="onboarding-feature-icon">📄</span>
            <span>Full research papers in IEEE/ACM/Springer format</span>
          </div>
          <div class="onboarding-feature-item">
            <span class="onboarding-feature-icon">🔬</span>
            <span>Literature surveys with taxonomy & timeline</span>
          </div>
          <div class="onboarding-feature-item">
            <span class="onboarding-feature-icon">🤖</span>
            <span>AI agent chat with web search & tool calling</span>
          </div>
          <div class="onboarding-feature-item">
            <span class="onboarding-feature-icon">✅</span>
            <span>Code reproducibility & claim verification</span>
          </div>
        </div>
        <div class="onboarding-welcome-checkbox">
          <label>
            <input type="checkbox" id="onboardingDontShowAgain" />
            <span>Don't show this again</span>
          </label>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    document.getElementById("onboardingStartTourBtn")?.addEventListener("click", () => {
      closeWelcomeOverlay();
      startTour();
    });
    document.getElementById("onboardingExploreBtn")?.addEventListener("click", () => {
      closeWelcomeOverlay();
      _completeOnboarding();
    });
    document.getElementById("onboardingSampleTopicsBtn")?.addEventListener("click", () => {
      closeWelcomeOverlay();
      _completeOnboarding();
      showSampleTopics();
    });
    
    // Close on click outside
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        closeWelcomeOverlay();
        _completeOnboarding();
      }
    });
  }

  function closeWelcomeOverlay() {
    const overlay = document.getElementById("onboardingWelcomeOverlay");
    if (overlay) overlay.remove();
  }

  function _completeOnboarding() {
    const dontShow = document.getElementById("onboardingDontShowAgain")?.checked;
    if (dontShow) {
      localStorage.setItem(ONBOARDING_KEY, "true");
      _onboardingComplete = true;
    }
  }

  // ── Tour Elements ──────────────────────────────────────────────────────
  function createTourElements() {
    // Backdrop overlay
    _tourOverlay = document.createElement("div");
    _tourOverlay.id = "tourOverlay";
    _tourOverlay.className = "tour-overlay hidden";
    document.body.appendChild(_tourOverlay);

    // Tooltip popup
    _tourTooltip = document.createElement("div");
    _tourTooltip.id = "tourTooltip";
    _tourTooltip.className = "tour-tooltip hidden";
    _tourTooltip.innerHTML = `
      <div class="tour-tooltip-header">
        <span class="tour-step-indicator"></span>
        <button class="tour-close-btn" title="Close tour" type="button">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="tour-tooltip-body">
        <h3 class="tour-tooltip-title"></h3>
        <p class="tour-tooltip-content"></p>
      </div>
      <div class="tour-tooltip-footer">
        <div class="tour-dots"></div>
        <div class="tour-actions">
          <button class="tour-prev-btn" type="button">Back</button>
          <button class="tour-next-btn primary" type="button">Next</button>
        </div>
      </div>
    `;
    document.body.appendChild(_tourTooltip);

    // Wire tour buttons
    _tourTooltip.querySelector(".tour-close-btn")?.addEventListener("click", endTour);
    _tourTooltip.querySelector(".tour-prev-btn")?.addEventListener("click", () => goToStep(_currentStep - 1));
    _tourTooltip.querySelector(".tour-next-btn")?.addEventListener("click", () => goToStep(_currentStep + 1));
  }

  function startTour() {
    _tourActive = true;
    _currentStep = 0;
    _tourOverlay?.classList.remove("hidden");
    goToStep(0);
  }

  function goToStep(index) {
    if (index < 0 || index >= TOUR_STEPS.length) {
      endTour();
      return;
    }
    _currentStep = index;
    const step = TOUR_STEPS[index];

    // Call onEnter callback if defined
    if (step.onEnter) step.onEnter();

    // Remove previous highlight
    document.querySelectorAll(".tour-highlight").forEach(el => el.classList.remove("tour-highlight"));

    // Find target element
    const target = document.querySelector(step.target);
    if (!target) {
      // Skip to next if target not found
      goToStep(index + 1);
      return;
    }

    // Add highlight class to target
    target.classList.add("tour-highlight");
    target.scrollIntoView({ behavior: "smooth", block: "nearest" });

    // Update tooltip content
    const titleEl = _tourTooltip?.querySelector(".tour-tooltip-title");
    const contentEl = _tourTooltip?.querySelector(".tour-tooltip-content");
    const indicatorEl = _tourTooltip?.querySelector(".tour-step-indicator");
    if (titleEl) titleEl.textContent = step.title;
    if (contentEl) contentEl.textContent = step.content;
    if (indicatorEl) indicatorEl.textContent = `${index + 1} / ${TOUR_STEPS.length}`;

    // Update dots
    const dotsContainer = _tourTooltip?.querySelector(".tour-dots");
    if (dotsContainer) {
      dotsContainer.innerHTML = TOUR_STEPS.map((_, i) =>
        `<span class="tour-dot ${i === index ? 'active' : ''}"></span>`
      ).join("");
    }

    // Update button states
    const prevBtn = _tourTooltip?.querySelector(".tour-prev-btn");
    const nextBtn = _tourTooltip?.querySelector(".tour-next-btn");
    if (prevBtn) prevBtn.disabled = index === 0;
    if (nextBtn) {
      if (index === TOUR_STEPS.length - 1) {
        nextBtn.textContent = "Finish ✓";
      } else {
        nextBtn.textContent = "Next →";
      }
    }

    // Position the tooltip near the target
    positionTooltip(target, step.placement || "bottom");

    // Show tooltip
    _tourTooltip?.classList.remove("hidden");
  }

  function positionTooltip(target, placement) {
    if (!_tourTooltip || !target) return;
    const targetRect = target.getBoundingClientRect();
    const tooltipEl = _tourTooltip;
    const tooltipWidth = 340;
    const tooltipHeight = tooltipEl.offsetHeight || 280;
    const gap = 12;
    let top, left, arrowPlacement;

    switch (placement) {
      case "right":
        left = Math.min(targetRect.right + gap, window.innerWidth - tooltipWidth - 20);
        top = Math.max(20, targetRect.top + (targetRect.height / 2) - (tooltipHeight / 2));
        arrowPlacement = "left";
        break;
      case "left":
        left = Math.max(20, targetRect.left - tooltipWidth - gap);
        top = Math.max(20, targetRect.top + (targetRect.height / 2) - (tooltipHeight / 2));
        arrowPlacement = "right";
        break;
      case "top":
        left = Math.max(20, targetRect.left + (targetRect.width / 2) - (tooltipWidth / 2));
        top = Math.max(20, targetRect.top - tooltipHeight - gap);
        arrowPlacement = "bottom";
        break;
      case "bottom":
      default:
        left = Math.max(20, targetRect.left + (targetRect.width / 2) - (tooltipWidth / 2));
        top = Math.min(targetRect.bottom + gap, window.innerHeight - tooltipHeight - 20);
        arrowPlacement = "top";
        break;
    }

    // Clamp to viewport
    left = Math.max(20, Math.min(left, window.innerWidth - tooltipWidth - 20));
    top = Math.max(20, Math.min(top, window.innerHeight - tooltipHeight - 20));

    tooltipEl.style.left = left + "px";
    tooltipEl.style.top = top + "px";
    tooltipEl.setAttribute("data-placement", arrowPlacement);
  }

  function endTour() {
    _tourActive = false;
    _tourOverlay?.classList.add("hidden");
    _tourTooltip?.classList.add("hidden");
    document.querySelectorAll(".tour-highlight").forEach(el => el.classList.remove("tour-highlight"));
    localStorage.setItem(ONBOARDING_KEY, "true");
    _onboardingComplete = true;
  }

  // ── Tooltips ───────────────────────────────────────────────────────────
  function createTooltipElements() {
    const style = document.createElement("style");
    style.textContent = `
      .ctx-tooltip {
        position: fixed;
        z-index: 9998;
        background: rgba(20, 20, 25, 0.97);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 8px;
        padding: 10px 14px;
        max-width: 280px;
        font-size: 0.72rem;
        line-height: 1.5;
        color: #d4d4d8;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(139, 92, 246, 0.1);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.2s ease, transform 0.2s ease;
        transform: translateY(4px);
        animation: fadeIn 0.2s ease forwards;
      }
      .ctx-tooltip.visible {
        opacity: 1;
        transform: translateY(0);
      }
      .ctx-tooltip .ctx-tt-title {
        display: block;
        font-weight: 700;
        font-size: 0.75rem;
        color: #c4b5fd;
        margin-bottom: 2px;
      }
      .ctx-tooltip .ctx-tt-desc {
        display: block;
        opacity: 0.8;
      }
    `;
    document.head.appendChild(style);

    // Attach hover listeners to each tooltip element
    TOOLTIPS.forEach(([selector, title, desc]) => {
      const el = document.querySelector(selector);
      if (!el) return;

      let tooltipEl = null;
      let hideTimeout = null;

      function showTooltip(e) {
        if (hideTimeout) clearTimeout(hideTimeout);
        if (!tooltipEl) {
          tooltipEl = document.createElement("div");
          tooltipEl.className = "ctx-tooltip";
          tooltipEl.innerHTML = `<span class="ctx-tt-title">${title}</span><span class="ctx-tt-desc">${desc}</span>`;
          document.body.appendChild(tooltipEl);
        }
        const rect = el.getBoundingClientRect();
        tooltipEl.style.left = Math.max(10, rect.left + rect.width / 2 - 140) + "px";
        tooltipEl.style.top = (rect.bottom + 10) + "px";
        tooltipEl.classList.add("visible");
      }

      function hideTooltip() {
        hideTimeout = setTimeout(() => {
          if (tooltipEl) {
            tooltipEl.classList.remove("visible");
          }
        }, 100);
      }

      el.addEventListener("mouseenter", showTooltip);
      el.addEventListener("mouseleave", hideTooltip);
      el.addEventListener("focus", showTooltip);
      el.addEventListener("blur", hideTooltip);
    });
  }

  // ── Sample Topics Panel ────────────────────────────────────────────────
  function createSampleTopicsPanel() {
    // Add sample topics button to the sidebar
    const configPanel = document.querySelector(".config-panel");
    if (!configPanel) return;

    const panel = document.createElement("div");
    panel.className = "panel sample-topics-panel";
    panel.id = "sampleTopicsPanel";
    panel.innerHTML = `
      <header class="panel-header" style="cursor: pointer;" id="sampleTopicsHeader">
        <h2>Quick Start</h2>
        <span class="badge small" style="font-size: 0.55rem; background: rgba(16,185,129,0.15); color: #34d399;">Sample Topics</span>
      </header>
      <div id="sampleTopicsBody">
        <p style="font-size: 0.7rem; color: #71717a; margin: 0 0 8px 0; line-height: 1.4;">
          Click a topic to pre-fill the chat and launch research instantly:
        </p>
        <div id="sampleTopicsList" class="sample-topics-list">
          ${SAMPLE_TOPICS.map((t, i) => `
            <button class="sample-topic-btn" data-index="${i}" type="button" title="${t.topic}">
              <span class="sample-topic-title">${t.title}</span>
              <span class="sample-topic-subtitle">${t.subtitle}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;

    // Insert after config panel
    configPanel.parentNode?.insertBefore(panel, configPanel.nextSibling);

    // Wire sample topic buttons
    document.querySelectorAll(".sample-topic-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index);
        const topic = SAMPLE_TOPICS[idx];
        if (!topic) return;

        // Set configuration
        if (templateSelect) templateSelect.value = topic.template;
        if (depthSelect) depthSelect.value = topic.depth;

        // Select the correct mode
        const modeRadio = document.querySelector(`input[name="runMode"][value="${topic.mode}"]`);
        if (modeRadio) modeRadio.click();

        // Fill the message input
        if (messageInput) {
          messageInput.value = topic.topic;
          messageInput.focus();
        }

        // Flash the send button
        const sendBtn = document.getElementById("sendBtn");
        if (sendBtn) {
          sendBtn.style.boxShadow = "0 0 25px rgba(139, 92, 246, 0.6)";
          sendBtn.style.transform = "scale(1.05)";
          setTimeout(() => {
            sendBtn.style.boxShadow = "";
            sendBtn.style.transform = "";
          }, 1000);
        }
      });
    });

    // Wire collapse toggle
    document.getElementById("sampleTopicsHeader")?.addEventListener("click", () => {
      const body = document.getElementById("sampleTopicsBody");
      if (body) body.classList.toggle("hidden");
    });
  }

  function showSampleTopics() {
    const panel = document.getElementById("sampleTopicsPanel");
    if (panel) {
      const body = document.getElementById("sampleTopicsBody");
      if (body) body.classList.remove("hidden");
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  // ── Expose public API ──────────────────────────────────────────────────
  window.startTour = startTour;
  window.showSampleTopics = showSampleTopics;

  // ── Start ──────────────────────────────────────────────────────────────
  init();

})();
