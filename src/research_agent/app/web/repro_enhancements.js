// ── Reproducibility Filtering, Search, Export & Run History (P29) ──────────────

let _reproFilter = "all";
let _reproSearchQuery = "";
let _reproSort = "default";

const reproFilterChips = document.querySelectorAll(".repro-filter-chip");
const reproClaimSearch = document.getElementById("reproClaimSearch");
const reproSortSelect = document.getElementById("reproSortSelect");
const reproDownloadReportBtn = document.getElementById("reproDownloadReportBtn");
const reproDownloadJsonBtn = document.getElementById("reproDownloadJsonBtn");
const reproRunHistory = document.getElementById("reproRunHistory");

// ── Reproducibility Tooltip System ─────────────────────────────────

const _reproTooltipDefs = [
  { selector: ".score-overall", title: "Overall Score", desc: "Aggregate reproducibility score across all verified claims, weighted by confidence." },
  { selector: ".score-pass", title: "Passed Claims", desc: "Claims where the actual computed value matched the claimed value within tolerance." },
  { selector: ".score-fail", title: "Failed Claims", desc: "Claims where the actual value significantly differed from the claimed value." },
  { selector: ".score-partial", title: "Partial Matches", desc: "Claims where the result was neither a clear pass nor fail (e.g., approximate match)." },
  { selector: ".score-unverifiable", title: "Unverifiable Claims", desc: "Claims that could not be tested (missing code, ambiguous measurement, external dependency)." },
  { selector: "#reproDownloadReportBtn", title: "Download Report", desc: "Download the full reproducibility report as a Markdown (.md) file." },
  { selector: "#reproDownloadJsonBtn", title: "JSON Export", desc: "Export the raw reproducibility data as a JSON file for programmatic analysis." },
  { selector: "#reproViewReportBtn", title: "View Report", desc: "Open the full reproducibility report in a modal for reading and copying." },
  { selector: "#reproViewScriptsBtn", title: "Scripts", desc: "View the verification scripts that were executed to test each claim." },
  { selector: '.repro-filter-chip[data-filter="all"]', title: "All Claims", desc: "Show all claims regardless of verification status." },
  { selector: '.repro-filter-chip[data-filter="pass"]', title: "Passed", desc: "Show only claims where the computed value matched the claimed value within tolerance." },
  { selector: '.repro-filter-chip[data-filter="fail"]', title: "Failed", desc: "Show only claims where the actual value differed significantly from the claimed value." },
  { selector: '.repro-filter-chip[data-filter="partial"]', title: "Partial", desc: "Show only claims with approximate or partial matches." },
  { selector: '.repro-filter-chip[data-filter="unverifiable"]', title: "Unverifiable", desc: "Show only claims that could not be verified (missing code, ambiguous values, etc.)." },
  { selector: ".repro-history-item", title: "Previous Run", desc: "Click to load reproducibility data from this previous research run for comparison." },
];

// History item tooltips need dynamic attachment (elements are replaced on each render)
// Extracted from _reproTooltipDefs to keep single source of truth
var _reproHistoryTooltipDef = null;
_reproTooltipDefs.forEach(function(d) {
  if (d.selector === ".repro-history-item") _reproHistoryTooltipDef = d;
});

let _reproTooltipsInitialized = false;

function _initReproTooltips() {
  if (_reproTooltipsInitialized) return;
  _reproTooltipsInitialized = true;
  
  // Skip .repro-history-item — handled dynamically in loadReproducibilityRunHistory
  var staticDefs = _reproTooltipDefs.filter(function(def) { return def.selector !== ".repro-history-item"; });
  
  staticDefs.forEach(function(def) {
    var els = document.querySelectorAll(def.selector);
    els.forEach(function(el) {
      el.addEventListener("mouseenter", function(e) {
        _showReproTooltip(e, def.title, def.desc);
      });
      el.addEventListener("mouseleave", _hideReproTooltip);
    });
  });
}

var _reproTooltipEl = null;
var _reproTooltipHideTimer = null;

function _showReproTooltip(e, title, desc) {
  if (_reproTooltipHideTimer) clearTimeout(_reproTooltipHideTimer);
  if (!_reproTooltipEl) {
    _reproTooltipEl = document.createElement("div");
    _reproTooltipEl.className = "repro-tooltip";
    document.body.appendChild(_reproTooltipEl);
  }
  _reproTooltipEl.innerHTML = '<span class="repro-tooltip-title">' + title + '</span><span class="repro-tooltip-desc">' + desc + '</span>';
  
  var rect = (e.currentTarget || e.target).getBoundingClientRect();
  var tooltipW = 260;
  var left = Math.max(10, Math.min(rect.left + rect.width / 2 - tooltipW / 2, window.innerWidth - tooltipW - 10));
  var top = rect.bottom + 10;
  _reproTooltipEl.style.left = left + "px";
  _reproTooltipEl.style.top = top + "px";
  _reproTooltipEl.classList.add("visible");
}

function _hideReproTooltip() {
  _reproTooltipHideTimer = setTimeout(function() {
    if (_reproTooltipEl) _reproTooltipEl.classList.remove("visible");
  }, 80);
}

// Init tooltips on DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", _initReproTooltips);
} else {
  _initReproTooltips();
}

// ── Staggered animation for claim cards ────────────────────────────

function _applyStaggeredAnimations(container) {
  if (!container) return;
  var cards = container.querySelectorAll(".repro-claim-card");
  cards.forEach(function(card, i) {
    card.style.animation = "staggerFadeIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards";
    card.style.animationDelay = (i * 0.06) + "s";
    card.style.opacity = "0";
  });
}

// ── Patch the score card update to add icons ───────────────────────

function _updateScoreCardIcons() {
  var scoreCards = document.querySelectorAll(".repro-score-card");
  if (!scoreCards.length) return;
  
  var iconMap = {
    "Overall Score": "📊",
    "Passed": "✅",
    "Failed": "❌",
    "Partial": "🟡",
    "Unverifiable": "⬜"
  };
  
  scoreCards.forEach(function(card) {
    var labelEl = card.querySelector(".repro-score-label");
    if (!labelEl) return;
    var label = labelEl.textContent.trim();
    if (iconMap[label] && !card.querySelector(".repro-score-icon")) {
      var icon = document.createElement("span");
      icon.className = "repro-score-icon";
      icon.textContent = iconMap[label];
      card.insertBefore(icon, card.firstChild);
    }
  });
}

function updateFilteredClaims() {
  if (!_reproDataCache || !_reproDataCache.items) return;
  let items = [..._reproDataCache.items];
  
  // Apply status filter
  if (_reproFilter !== "all") {
    items = items.filter(item => item.status === _reproFilter);
  }
  
  // Apply search query
  if (_reproSearchQuery.trim()) {
    const q = _reproSearchQuery.toLowerCase().trim();
    items = items.filter(item => {
      return (item.claim_text || "").toLowerCase().includes(q)
        || (item.claimed_value || "").toLowerCase().includes(q)
        || (item.actual_value || "").toLowerCase().includes(q);
    });
  }
  
  // Apply sorting
  if (_reproSort === "confidence-desc") {
    items.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
  } else if (_reproSort === "confidence-asc") {
    items.sort((a, b) => (a.confidence || 0) - (b.confidence || 0));
  } else if (_reproSort === "runtime-desc") {
    items.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
  } else if (_reproSort === "runtime-asc") {
    items.sort((a, b) => (a.duration_seconds || 0) - (b.duration_seconds || 0));
  } else if (_reproSort === "alpha") {
    items.sort((a, b) => (a.claim_text || "").localeCompare(b.claim_text || ""));
  }
  
  // Update count badge on status text
  if (reproducibilityStatusText) {
    const total = _reproDataCache.total_claims || 0;
    const filtered = items.length;
    if (filtered === total) {
      reproducibilityStatusText.textContent = total + " claims analyzed";
    } else {
      reproducibilityStatusText.textContent = filtered + "/" + total + " claims (filtered)";
    }
  }
  
  // Re-render claims
  if (reproClaimsContainer) {
    if (items.length === 0) {
      reproClaimsContainer.innerHTML = "<p class='small muted'>No claims match the current filter.</p>";
      return;
    }
    
    reproClaimsContainer.innerHTML = items.map((item) => {
      const status = item.status || "unknown";
      const statusEmoji = status === "pass" ? "\u2705" : status === "fail" ? "\u274c" : status === "partial" ? "\U0001f7e1" : "\u2b1c";
      const statusColor = status === "pass" ? "#34d399" : status === "fail" ? "#f43f5e" : status === "partial" ? "#f59e0b" : "#71717a";
      const claimText = item.claim_text || "Unknown claim";
      const claimedVal = item.claimed_value || "\u2014";
      const actualVal = item.actual_value || "\u2014";
      const confidence = item.confidence || 0;
      const duration = item.duration_seconds || 0;

      return `
        <div class="repro-claim-card">
          <div style="display: flex; align-items: flex-start; gap: 10px;">
            <span style="font-size: 1.1rem; line-height: 1.4;">${statusEmoji}</span>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 0.8rem; color: #e4e4e7; line-height: 1.4; margin-bottom: 6px;" title="${claimText.replace(/"/g, "&quot;")}">${claimText}</div>
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
    
    // Apply staggered animations to newly rendered claims
    _applyStaggeredAnimations(reproClaimsContainer);
  }
}

// ── Event listeners for filters, search, sort ──

reproFilterChips.forEach(chip => {
  chip.addEventListener("click", () => {
    reproFilterChips.forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    _reproFilter = chip.dataset.filter;
    updateFilteredClaims();
  });
});

reproClaimSearch?.addEventListener("input", (e) => {
  _reproSearchQuery = e.target.value;
  updateFilteredClaims();
});

reproSortSelect?.addEventListener("change", (e) => {
  _reproSort = e.target.value;
  updateFilteredClaims();
});

// ── Export / Download functions ──

async function downloadReproducibilityReport() {
  if (!currentRunId) {
    appendMessage("assistant", "No research run loaded.");
    return;
  }
  try {
    const res = await fetch(`/api/runs/${currentRunId}/reproducibility/report`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Report not found");
    const data = await res.json();
    const reportText = data.report || "No report content.";
    const blob = new Blob([reportText], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reproducibility_report_${currentRunId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Download report failed:", err);
  }
}

async function downloadReproducibilityJson() {
  if (!currentRunId || !_reproDataCache) {
    appendMessage("assistant", "No reproducibility data loaded.");
    return;
  }
  const jsonStr = JSON.stringify(_reproDataCache, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `reproducibility_data_${currentRunId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Run History Comparison ──

async function loadReproducibilityRunHistory() {
  if (!reproRunHistory) return;
  
  try {
    const res = await fetch("/api/sessions", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Failed to fetch sessions");
    const sessionsData = await res.json();
    const sessions = sessionsData.sessions || [];
    
    const runPromises = sessions
      .filter(s => s.last_run_id && s.last_run_id !== currentRunId)
      .slice(0, 10)
      .map(async (s) => {
        try {
          const r = await fetch(`/api/runs/${s.last_run_id}/reproducibility`, {
            headers: { "Authorization": `Bearer ${authToken}` }
          });
          if (!r.ok) return null;
          const d = await r.json();
          if (!d.has_reproducibility) return null;
          return {
            run_id: s.last_run_id,
            topic: s.topic || "Untitled",
            overall_score: d.overall_score || 0,
            passed: d.summary?.passed || 0,
            failed: d.summary?.failed || 0,
            total: d.total_claims || 0,
          };
        } catch {
          return null;
        }
      });
    
    const results = (await Promise.all(runPromises)).filter(Boolean);
    
    if (results.length === 0) {
      reproRunHistory.innerHTML = '<p class="small muted" style="margin: 0; font-size: 0.7rem;">No previous runs with reproducibility data found.</p>';
      return;
    }
    
    reproRunHistory.innerHTML = results.map(r => {
      const scorePct = (r.overall_score * 100).toFixed(0);
      const scoreColor = r.overall_score >= 0.8 ? "#34d399" : r.overall_score >= 0.5 ? "#f59e0b" : "#f43f5e";
      return `
        <div class="repro-history-item" style="display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.2s;" data-run-id="${r.run_id}" title="Click to load this run">
          <span style="font-size: 0.65rem; font-weight: 700; color: ${scoreColor};">${scorePct}%</span>
          <div style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <div style="font-size: 0.65rem; color: #d4d4d8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${r.topic}">${r.topic}</div>
            <div style="font-size: 0.6rem; color: #52525b;">${r.passed} ✅ / ${r.failed} ❌ | ${r.run_id.slice(0, 12)}...</div>
          </div>
        </div>
      `;
    }).join("");
    
    reproRunHistory.querySelectorAll(".repro-history-item").forEach(el => {
      el.addEventListener("click", () => {
        const runId = el.dataset.runId;
        if (runId) {
          currentRunId = runId;
          loadReproducibilityData();
        }
      });
      // Dynamically attach tooltip (elements are recreated on each render)
      el.addEventListener("mouseenter", function(e) {
        _showReproTooltip(e, _reproHistoryTooltipDef.title, _reproHistoryTooltipDef.desc);
      });
      el.addEventListener("mouseleave", _hideReproTooltip);
    });
    
    // Apply staggered animation to history items
    _applyStaggeredAnimations(reproRunHistory);
  } catch (err) {
    console.error("Failed to load run history:", err);
    reproRunHistory.innerHTML = '<p class="small muted" style="margin: 0; font-size: 0.7rem;">Unable to load run history.</p>';
  }
}

// ── Wire up export buttons ──

reproDownloadReportBtn?.addEventListener("click", downloadReproducibilityReport);
reproDownloadJsonBtn?.addEventListener("click", downloadReproducibilityJson);

// ── Patch renderReproducibilityDashboard to reset filters and load history ──

const _origRenderDashboard = window.renderReproducibilityDashboard;
window.renderReproducibilityDashboard = function(data) {
  _origRenderDashboard(data);
  _reproFilter = "all";
  _reproSearchQuery = "";
  _reproSort = "default";
  if (reproClaimSearch) reproClaimSearch.value = "";
  if (reproSortSelect) reproSortSelect.value = "default";
  reproFilterChips.forEach(c => {
    c.classList.toggle("active", c.dataset.filter === "all");
  });
  _updateScoreCardIcons();
  _initReproTooltips();
  loadReproducibilityRunHistory();
};
