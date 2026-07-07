/**
 * P36 — Paper-git Frontend
 * Version control for research documents: timeline, branches, PR review, diff viewer
 */

// ── State ───────────────────────────────────────────────────────────────────
let _pgSnapshots = [];
let _pgBranches = [];
let _pgPrs = [];
let _pgSelectedBranch = null;
let _pgSelectedPrId = null;
let _pgActiveSubTab = "timeline";

function _pgAuthToken() {
  return localStorage.getItem("research_auth_token") || "";
}
function _pgAuthHeaders() {
  return { "Authorization": `Bearer ${_pgAuthToken()}`, "Content-Type": "application/json" };
}
function _pgAuthPlain() {
  return { "Authorization": `Bearer ${_pgAuthToken()}` };
}

// ── Inline Status Helper (replaces alerts) ────────────────────────────
function _pgStatus(msg) {
  const el = document.getElementById("pgStatsText");
  if (el) el.textContent = msg;
}

// ── Entry Point ─────────────────────────────────────────────────────────────
async function loadPaperGitBrowser() {
  const panel = document.querySelector("#paperGitWorkbench");
  if (!panel) return;
  await Promise.all([_pgLoadStats(), _pgLoadSnapshots(), _pgLoadBranches(), _pgLoadPrs()]);
}

// ── Stats ──────────────────────────────────────────────────────────────────
async function _pgLoadStats() {
  try {
    const res = await fetch("/api/paper-git/stats/summary", { headers: _pgAuthPlain() });
    if (!res.ok) return;
    const stats = await res.json();
    const el = document.getElementById("pgStatsText");
    if (el) el.textContent = `${stats.total_snapshots || 0} snapshots, ${stats.total_branches || 0} branches, ${stats.total_pull_requests || 0} PRs`;
  } catch (e) { /* ignore */ }
}

// ── Sub-tab Switching ──────────────────────────────────────────────────────
function _pgSwitchSubTab(tab) {
  _pgActiveSubTab = tab;
  ["pgTimelineTab", "pgBranchesTab", "pgPrsTab", "pgDiffTab"].forEach(id => {
    document.getElementById(id)?.classList.toggle("active", id.replace("Tab", "").toLowerCase().includes(tab));
  });
  ["pgTimelinePanel", "pgBranchesPanel", "pgPrsPanel", "pgDiffPanel"].forEach(id => {
    document.getElementById(id)?.classList.toggle("active", id.replace("Panel", "").toLowerCase().includes(tab));
  });
  if (tab === "timeline") _pgLoadSnapshots();
  if (tab === "branches") _pgLoadBranches();
  if (tab === "prs") _pgLoadPrs();
}

// ── Snapshots Timeline ─────────────────────────────────────────────────────
async function _pgLoadSnapshots() {
  try {
    const filter = document.getElementById("pgTimelineBranchFilter")?.value || "";
    const params = filter ? `?branch=${encodeURIComponent(filter)}` : "";
    const res = await fetch(`/api/paper-git/snapshots${params}`, { headers: _pgAuthPlain() });
    _pgSnapshots = res.ok ? await res.json() : [];
    _pgRenderTimeline();
    _pgPopulateDiffSelectors();
  } catch (e) { _pgSnapshots = []; }
}

function _pgRenderTimeline() {
  const container = document.getElementById("pgTimelineContainer");
  const countEl = document.getElementById("pgSnapshotCount");
  if (!container) return;
  if (countEl) countEl.textContent = _pgSnapshots.length;

  if (_pgSnapshots.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">No snapshots yet. Run a research paper to create snapshots.</p>';
    return;
  }

  // Group by branch
  const grouped = {};
  _pgSnapshots.forEach(s => {
    const b = s.branch || "main";
    if (!grouped[b]) grouped[b] = [];
    grouped[b].push(s);
  });

  container.innerHTML = Object.entries(grouped).map(([branch, snaps]) => {
    const color = branch === "main" ? "#8b5cf6" : "#06b6d4";
    return `
      <div class="pg-timeline-branch-group">
        <div class="pg-timeline-branch-header" style="border-left: 3px solid ${color}; padding-left: 10px; margin-bottom: 8px;">
          <span class="mono small" style="font-weight: 700;">&#x1F33F; ${_pgEsc(branch)}</span>
          <span class="mono small" style="color: var(--muted);">${snaps.length} version(s)</span>
        </div>
        <div class="pg-timeline-entries">
          ${snaps.map((s, i) => {
            const isLatest = i === 0;
            const date = s.created_at ? new Date(s.created_at).toLocaleString() : "unknown";
            return `
              <div class="pg-timeline-entry ${isLatest ? "latest" : ""}">
                <div class="pg-timeline-dot" style="background: ${color};"></div>
                <div class="pg-timeline-content">
                  <div class="pg-timeline-msg">${_pgEsc(s.message || "No message")}</div>
                  <div class="pg-timeline-meta">
                    <span class="mono small muted">${s.id ? s.id.slice(0, 12) + "..." : ""}</span>
                    <span class="mono small muted">${date}</span>
                    ${s.tags && s.tags.length ? `<span class="pg-tag">${s.tags[0]}</span>` : ""}
                  </div>
                  <div class="pg-timeline-actions">
                    <button class="btn-icon small" onclick="_pgDiffFromSnapshot('${s.id}')" title="Diff from this snapshot">&#x1F50D;</button>
                    <button class="btn-icon small" onclick="_pgRestoreSnapshot('${s.id}')" title="Restore to this snapshot">&#x21A9;&#xFE0F;</button>
                  </div>
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function _pgDiffFromSnapshot(snapId) {
  // Switch to diff tab and set this as old snapshot
  _pgSwitchSubTab("diff");
  const oldSelect = document.getElementById("pgDiffOldSnapshot");
  if (oldSelect) oldSelect.value = snapId;
}

async function _pgRestoreSnapshot(snapId) {
  if (!confirm("Restore to this snapshot? Current files will be overwritten.")) return;
  try {
    const snap = _pgSnapshots.find(s => s.id === snapId);
    const runId = snap?.run_id || "unknown";
    await fetch(`/api/paper-git/restores?snapshot_id=${snapId}&run_id=${runId}`, {
      method: "POST",
      headers: _pgAuthPlain()
    });
    _pgStatus("Restored successfully!");
  } catch (e) {
    const _pgStatusEl = document.getElementById("pgStatsText"); if (_pgStatusEl) _pgStatusEl.textContent = "Restore failed: " + e.message;
  }
}

// ── Branches ───────────────────────────────────────────────────────────────
async function _pgLoadBranches() {
  try {
    const res = await fetch("/api/paper-git/branches", { headers: _pgAuthPlain() });
    _pgBranches = res.ok ? await res.json() : [];
    _pgRenderBranches();
    _pgPopulateBranchFilter();
  } catch (e) { _pgBranches = []; }
}

function _pgRenderBranches() {
  const container = document.getElementById("pgBranchesContainer");
  const countEl = document.getElementById("pgBranchCount");
  if (!container) return;
  if (countEl) countEl.textContent = _pgBranches.length;

  if (_pgBranches.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 12px; text-align: center;">No branches yet.</p>';
    return;
  }

  container.innerHTML = _pgBranches.map(b => {
    const isSelected = _pgSelectedBranch === b.name;
    return `
      <div class="pg-branch-item ${isSelected ? "selected" : ""}" onclick="_pgSelectBranch('${b.name}')" style="border-left: 3px solid ${b.name === "main" ? "#8b5cf6" : "#06b6d4"};">
        <div class="pg-branch-item-name">${_pgEsc(b.name)}</div>
        <div class="pg-branch-item-meta mono small muted">${b.head_snapshot_id ? b.head_snapshot_id.slice(0, 12) + "..." : "no snapshots"}</div>
      </div>
    `;
  }).join("");

  // Auto-select first
  if (!_pgSelectedBranch && _pgBranches.length > 0) {
    _pgSelectBranch(_pgBranches[0].name);
  }
}

async function _pgSelectBranch(name) {
  _pgSelectedBranch = name;
  _pgRenderBranches();

  const b = _pgBranches.find(x => x.name === name);
  if (!b) return;

  document.getElementById("pgBranchEmpty")?.classList.add("hidden");
  document.getElementById("pgBranchContent")?.classList.remove("hidden");
  document.getElementById("pgBranchDetailName").textContent = b.name;
  document.getElementById("pgBranchDetailMeta").textContent = `Created: ${b.created_at ? new Date(b.created_at).toLocaleDateString() : "N/A"}`;

  // Load snapshots for this branch
  try {
    const res = await fetch(`/api/paper-git/snapshots?branch=${encodeURIComponent(name)}`, { headers: _pgAuthPlain() });
    const snaps = res.ok ? await res.json() : [];
    const container = document.getElementById("pgBranchSnapshots");
    if (container) {
      container.innerHTML = snaps.slice(0, 10).map(s => `
        <div class="pg-branch-snap-entry mono small" style="padding: 4px 8px; background: rgba(255,255,255,0.02); border-radius: var(--radius-sm); margin-bottom: 4px;">
          <span style="color: #e4e4e7;">${_pgEsc(s.message || "No message")}</span>
          <span class="muted"> - ${s.created_at ? new Date(s.created_at).toLocaleDateString() : ""}</span>
        </div>
      `).join("") || '<p class="small muted">No snapshots on this branch.</p>';
    }
  } catch (e) { /* ignore */ }
}

function _pgPopulateBranchFilter() {
  const sel = document.getElementById("pgTimelineBranchFilter");
  if (!sel) return;
  sel.innerHTML = '<option value="">All Branches</option>' +
    _pgBranches.map(b => `<option value="${_pgEsc(b.name)}">${_pgEsc(b.name)}</option>`).join("");
}

async function _pgCreateBranch() {
  const name = prompt("Enter new branch name:");
  if (!name) return;
  const fromSnap = _pgSnapshots[0];
  if (!fromSnap) { _pgStatus("No snapshots to branch from. Create a snapshot first."); return; }
  try {
    await fetch(`/api/paper-git/branches?name=${encodeURIComponent(name)}&from_snapshot_id=${fromSnap.id}`, {
      method: "POST",
      headers: _pgAuthHeaders(),
      body: "{}"
    });
    await Promise.all([_pgLoadBranches(), _pgLoadStats()]);
  } catch (e) { const _pgSe = document.getElementById("pgStatsText"); _pgStatus("Failed to create branch: ") + e.message; }
}

async function _pgMergeBranch() {
  if (!_pgSelectedBranch || _pgSelectedBranch === "main") { _pgStatus("Cannot merge main into itself or no branch selected."); return; }
  const target = prompt(`Merge "${_pgSelectedBranch}" into which branch?`, "main");
  if (!target) return;
  const res = await fetch("/api/paper-git/merge", {
    method: "POST",
    headers: _pgAuthHeaders(),
    body: JSON.stringify({ source_branch: _pgSelectedBranch, target_branch: target, author: "user", message: `Merge ${_pgSelectedBranch} into ${target}` })
  });
  const result = await res.json();
  const _pgSe = document.getElementById("pgStatsText"); if (_pgSe) _pgStatus(result.message || "Merge completed");
  await Promise.all([_pgLoadBranches(), _pgLoadSnapshots(), _pgLoadStats()]);
}

// ── Pull Requests ──────────────────────────────────────────────────────────
async function _pgLoadPrs() {
  try {
    const status = document.getElementById("pgPrStatusFilter")?.value || "";
    const params = status ? `?status=${status}` : "";
    const res = await fetch(`/api/paper-git/prs${params}`, { headers: _pgAuthPlain() });
    _pgPrs = res.ok ? await res.json() : [];
    _pgRenderPrs();
  } catch (e) { _pgPrs = []; }
}

function _pgRenderPrs() {
  const container = document.getElementById("pgPrsList");
  if (!container) return;
  if (_pgPrs.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 12px;">No pull requests yet.</p>';
    return;
  }

  container.innerHTML = _pgPrs.map(pr => {
    const isSelected = pr.id === _pgSelectedPrId;
    const statusColor = pr.status === "open" ? "#34d399" : pr.status === "approved" ? "#8b5cf6" : pr.status === "merged" ? "#3b82f6" : pr.status === "changes_requested" ? "#f59e0b" : "#71717a";
    return `
      <div class="pg-pr-item ${isSelected ? "selected" : ""}" onclick="_pgSelectPr('${pr.id}')" style="border-left: 3px solid ${statusColor};">
        <div class="pg-pr-item-title">${_pgEsc(pr.title)}</div>
        <div class="pg-pr-item-meta mono small muted">
          ${pr.source_branch} &#x2192; ${pr.target_branch} &middot; ${pr.status}
        </div>
      </div>
    `;
  }).join("");

  if (!_pgSelectedPrId && _pgPrs.length > 0) {
    _pgSelectPr(_pgPrs[0].id);
  }
}

async function _pgSelectPr(prId) {
  _pgSelectedPrId = prId;
  _pgRenderPrs();

  try {
    const res = await fetch(`/api/paper-git/prs/${prId}`, { headers: _pgAuthPlain() });
    const pr = res.ok ? await res.json() : null;
    if (!pr) return;

    document.getElementById("pgPrEmpty")?.classList.add("hidden");
    document.getElementById("pgPrContent")?.classList.remove("hidden");

    document.getElementById("pgPrDetailTitle").textContent = pr.title || "Untitled PR";
    document.getElementById("pgPrDetailMeta").textContent = `#${pr.id.slice(0, 8)} by ${pr.author || "unknown"} | ${pr.source_branch} \u2192 ${pr.target_branch}`;
    document.getElementById("pgPrDetailDesc").textContent = pr.description || "No description provided.";

    // Status badge
    const badge = document.getElementById("pgPrStatusBadge");
    if (badge) {
      const statusColors = { open: "#34d399", approved: "#8b5cf6", changes_requested: "#f59e0b", merged: "#3b82f6", closed: "#71717a" };
      badge.textContent = pr.status?.toUpperCase() || "UNKNOWN";
      badge.style.background = `${statusColors[pr.status] || "#71717a"}20`;
      badge.style.color = statusColors[pr.status] || "#71717a";
      badge.style.border = `1px solid ${statusColors[pr.status] || "#71717a"}40`;
    }

    // Show/hide action buttons based on status
    const showActions = pr.status === "open";
    document.getElementById("pgPrApproveBtn")?.classList.toggle("hidden", !showActions);
    document.getElementById("pgPrRequestChangesBtn")?.classList.toggle("hidden", !showActions);
    document.getElementById("pgPrMergeBtn")?.classList.toggle("hidden", pr.status !== "approved");
    document.getElementById("pgPrCloseBtn")?.classList.toggle("hidden", pr.status === "merged" || pr.status === "closed");

    // Load diff preview
    _pgLoadPrDiff(prId);

    // Load comments
    _pgLoadPrComments(prId);

    // Load approvals
    const approvalsEl = document.getElementById("pgPrApprovalsList");
    const approvalCount = document.getElementById("pgPrApprovalCount");
    if (approvalsEl) {
      const approvals = pr.approvals || [];
      if (approvalCount) approvalCount.textContent = approvals.length;
      approvalsEl.innerHTML = approvals.length
        ? approvals.map(a => `<span class="pg-approval-badge">&#x2705; ${_pgEsc(a)}</span>`).join(" ")
        : '<p class="small muted">No approvals yet.</p>';
    }
  } catch (e) { /* ignore */ }
}

async function _pgLoadPrDiff(prId) {
  const container = document.getElementById("pgPrDiffContent");
  if (!container) return;
  try {
    const res = await fetch(`/api/paper-git/prs/${prId}/diff`, { headers: _pgAuthPlain() });
    const data = res.ok ? await res.json() : null;
    if (!data || !data.diff) { container.innerHTML = '<p class="small muted">No diff available.</p>'; return; }
    const d = data.diff;
    container.innerHTML = `
      <div class="pg-diff-summary-bar">${d.summary || "No changes"}</div>
      ${(d.files || []).map(f => `
        <div class="pg-diff-file">
          <div class="pg-diff-file-header">${_pgEsc(f.file_path)}</div>
          ${(f.hunks || []).slice(0, 3).map(h => `
            <pre class="pg-diff-hunk pg-diff-${h.kind}">${h.kind === "addition" ? "+" : h.kind === "deletion" ? "-" : "~"} ${_pgTrunc(_pgEsc((h.content || h.old_content || "").trim()), 120)}</pre>
          `).join("")}
          ${(f.hunks || []).length > 3 ? `<div class="small muted" style="padding: 4px 8px;">... ${(f.hunks || []).length - 3} more hunk(s)</div>` : ""}
        </div>`).join("")}
    `;
  } catch (e) {
    container.innerHTML = '<p class="small muted">Failed to load diff.</p>';
  }
}

async function _pgLoadPrComments(prId) {
  const container = document.getElementById("pgPrCommentsList");
  const countEl = document.getElementById("pgPrCommentCount");
  if (!container) return;
  try {
    const res = await fetch(`/api/paper-git/prs/${prId}/comments`, { headers: _pgAuthPlain() });
    const threads = res.ok ? await res.json() : [];
    const allComments = threads.flatMap(t => t.comments || []);
    if (countEl) countEl.textContent = allComments.length;

    if (allComments.length === 0) {
      container.innerHTML = '<p class="small muted">No comments yet.</p>';
      return;
    }

    container.innerHTML = allComments.map(c => `
      <div class="pg-comment-card ${c.resolved ? "resolved" : ""}">
        <div class="pg-comment-header">
          <span class="pg-comment-author">${_pgEsc(c.author)}</span>
          <span class="pg-comment-time mono small muted">${c.created_at ? new Date(c.created_at).toLocaleDateString() : ""}</span>
          ${c.file_path ? `<span class="pg-comment-file small muted">${_pgEsc(c.file_path)}</span>` : ""}
        </div>
        <div class="pg-comment-body">${_pgEsc(c.body)}</div>
        ${c.resolved ? '<span class="pg-resolved-badge">&#x2705; Resolved</span>' : ''}
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = '<p class="small muted">Failed to load comments.</p>';
  }
}

async function _pgAddPrComment() {
  if (!_pgSelectedPrId) return;
  const input = document.getElementById("pgPrCommentInput");
  const body = input?.value?.trim();
  if (!body) return;
  try {
    await fetch(`/api/paper-git/prs/${_pgSelectedPrId}/comment?body=${encodeURIComponent(body)}`, {
      method: "POST",
      headers: _pgAuthHeaders(),
      body: "{}"
    });
    input.value = "";
    _pgLoadPrComments(_pgSelectedPrId);
  } catch (e) { _pgStatus("Failed to add comment"); }
}

async function _pgApprovePr() {
  if (!_pgSelectedPrId) return;
  await fetch(`/api/paper-git/prs/${_pgSelectedPrId}/approve`, { method: "POST", headers: _pgAuthHeaders(), body: "{}" });
  _pgSelectPr(_pgSelectedPrId);
  _pgLoadPrs();
}

async function _pgRequestChanges() {
  if (!_pgSelectedPrId) return;
  const reason = prompt("Reason for changes:");
  if (reason === null) return;
  await fetch(`/api/paper-git/prs/${_pgSelectedPrId}/request-changes?reason=${encodeURIComponent(reason || "")}`, {
    method: "POST", headers: _pgAuthHeaders(), body: "{}"
  });
  _pgSelectPr(_pgSelectedPrId);
  _pgLoadPrs();
}

async function _pgMergePr() {
  if (!_pgSelectedPrId) return;
  if (!confirm("Merge this pull request?")) return;
  const res = await fetch(`/api/paper-git/prs/${_pgSelectedPrId}/merge`, { method: "POST", headers: _pgAuthHeaders(), body: "{}" });
  const result = await res.json();
  const _pgSe = document.getElementById("pgStatsText"); if (_pgSe) _pgStatus(result.message || "Merge completed");
  _pgSelectPr(_pgSelectedPrId);
  _pgLoadPrs();
  _pgLoadSnapshots();
  _pgLoadStats();
}

async function _pgClosePr() {
  if (!_pgSelectedPrId) return;
  await fetch(`/api/paper-git/prs/${_pgSelectedPrId}/close`, { method: "POST", headers: _pgAuthHeaders(), body: "{}" });
  _pgSelectPr(_pgSelectedPrId);
  _pgLoadPrs();
}

async function _pgCreatePr() {
  if (_pgBranches.length < 2) { _pgStatus("Need at least 2 branches to create a PR."); return; }
  const source = prompt("Source branch:", _pgBranches.find(b => b.name !== "main")?.name || "");
  const target = prompt("Target branch:", "main");
  const title = prompt("PR title:");
  if (!source || !target || !title) return;
  try {
    await fetch(`/api/paper-git/prs?title=${encodeURIComponent(title)}&source_branch=${encodeURIComponent(source)}&target_branch=${encodeURIComponent(target)}`, {
      method: "POST",
      headers: _pgAuthHeaders(),
      body: "{}"
    });
    _pgLoadPrs();
    _pgSwitchSubTab("prs");
    _pgLoadStats();
  } catch (e) { _pgStatus("Failed to create PR"); }
}

// ── Diff Viewer ────────────────────────────────────────────────────────────
function _pgPopulateDiffSelectors() {
  ["pgDiffOldSnapshot", "pgDiffNewSnapshot"].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">Select snapshot...</option>' +
      _pgSnapshots.map(s => {
        const label = `${s.id?.slice(0, 12) || ""} - ${(s.message || "No message").slice(0, 40)}`;
        return `<option value="${s.id}" ${s.id === current ? "selected" : ""}>${_pgEsc(label)}</option>`;
      }).join("");
  });
}

async function _pgCompareDiff() {
  const oldId = document.getElementById("pgDiffOldSnapshot")?.value;
  const newId = document.getElementById("pgDiffNewSnapshot")?.value;
  const container = document.getElementById("pgDiffResult");
  if (!oldId || !newId) { container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">Select both old and new snapshots.</p>'; return; }
  if (oldId === newId) { container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">Select two different snapshots.</p>'; return; }

  container.innerHTML = '<p style="padding: 20px; text-align: center;">Loading diff...</p>';

  try {
    const res = await fetch(`/api/paper-git/diff/${oldId}/${newId}`, { headers: _pgAuthPlain() });
    const diff = res.ok ? await res.json() : null;
    if (!diff) { container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">Failed to load diff.</p>'; return; }

    let html = `<div class="pg-diff-summary-bar">${diff.summary || "No changes"} | +${diff.stat_additions || 0} -${diff.stat_deletions || 0} | ${diff.stat_files_changed || 0} file(s)</div>`;

    (diff.files || []).forEach(f => {
      html += `<div class="pg-diff-file"><div class="pg-diff-file-header">${_pgEsc(f.file_path)}</div>`;
      (f.hunks || []).forEach(h => {
        const lines = h.kind === "addition" ? h.content : h.kind === "deletion" ? h.old_content : h.content;
        const prefix = h.kind === "addition" ? "+" : h.kind === "deletion" ? "-" : "~";
        const hClass = `pg-diff-${h.kind}`;
        html += `<pre class="pg-diff-hunk ${hClass}">`;
        (lines || "").split("\n").slice(0, 30).forEach(line => {
          html += `<span class="${hClass}">${prefix} ${_pgEsc(line)}</span>\n`;
        });
        if ((lines || "").split("\n").length > 30) {
          html += `<span class="muted">... truncated ...</span>`;
        }
        html += `</pre>`;
      });
      html += `</div>`;
    });

    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="small muted" style="padding: 20px; text-align: center;">Error: ${e.message}</p>`;
  }
}

async function _pgCreateSnapshot() {
  const runId = prompt("Run ID to snapshot (e.g. run-abc123):");
  if (!runId) { _pgStatus("A run ID is required to create a snapshot."); return; }
  try {
    await fetch(`/api/paper-git/snapshots?run_id=${encodeURIComponent(runId)}&message=${encodeURIComponent("Manual snapshot via UI")}&author=user`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${_pgAuthToken()}` },
    });
    await Promise.all([_pgLoadSnapshots(), _pgLoadStats()]);
    _pgStatus("Snapshot created!");
  } catch (e) { const _pgSe = document.getElementById("pgStatsText"); _pgStatus("Failed: ") + e.message; }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function _pgEsc(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function _pgTrunc(str, len) {
  if (!str || str.length <= len) return str || "";
  return str.slice(0, len) + "...";
}

// ── Event Binding ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Sub-tab switching
  document.getElementById("pgTimelineTab")?.addEventListener("click", () => _pgSwitchSubTab("timeline"));
  document.getElementById("pgBranchesTab")?.addEventListener("click", () => _pgSwitchSubTab("branches"));
  document.getElementById("pgPrsTab")?.addEventListener("click", () => _pgSwitchSubTab("prs"));
  document.getElementById("pgDiffTab")?.addEventListener("click", () => _pgSwitchSubTab("diff"));

  // Top bar actions
  document.getElementById("pgCreateSnapshotBtn")?.addEventListener("click", _pgCreateSnapshot);
  document.getElementById("pgCreateBranchBtn")?.addEventListener("click", _pgCreateBranch);
  document.getElementById("pgRefreshBtn")?.addEventListener("click", () => {
    _pgLoadStats(); _pgLoadSnapshots(); _pgLoadBranches(); _pgLoadPrs();
  });

  // Branch filter
  document.getElementById("pgTimelineBranchFilter")?.addEventListener("change", _pgLoadSnapshots);

  // Branch actions
  document.getElementById("pgBranchMergeBtn")?.addEventListener("click", _pgMergeBranch);
  document.getElementById("pgBranchCreatePrBtn")?.addEventListener("click", _pgCreatePr);
  document.getElementById("pgBranchDeleteBtn")?.addEventListener("click", async () => {
    if (!_pgSelectedBranch || _pgSelectedBranch === "main") { _pgStatus("Cannot delete main branch."); return; }
    if (!confirm(`Delete branch "${_pgSelectedBranch}"?`)) return;
    await fetch(`/api/paper-git/branches/${encodeURIComponent(_pgSelectedBranch)}`, { method: "DELETE", headers: _pgAuthPlain() });
    _pgSelectedBranch = null;
    _pgLoadBranches();
  });

  // PR actions
  document.getElementById("pgCreatePrBtn")?.addEventListener("click", _pgCreatePr);
  document.getElementById("pgPrApproveBtn")?.addEventListener("click", _pgApprovePr);
  document.getElementById("pgPrRequestChangesBtn")?.addEventListener("click", _pgRequestChanges);
  document.getElementById("pgPrMergeBtn")?.addEventListener("click", _pgMergePr);
  document.getElementById("pgPrCloseBtn")?.addEventListener("click", _pgClosePr);
  document.getElementById("pgPrCommentSubmit")?.addEventListener("click", _pgAddPrComment);
  document.getElementById("pgPrCommentInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") _pgAddPrComment();
  });
  document.getElementById("pgPrStatusFilter")?.addEventListener("change", _pgLoadPrs);
  document.getElementById("pgPrViewDiffBtn")?.addEventListener("click", () => {
    if (_pgSelectedPrId) _pgSwitchSubTab("diff");
  });

  // Diff viewer
  document.getElementById("pgDiffCompareBtn")?.addEventListener("click", _pgCompareDiff);
});
